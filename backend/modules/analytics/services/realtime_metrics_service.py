# backend/modules/analytics/services/realtime_metrics_service.py

import asyncio
import logging
import json
from typing import Dict, Any, List, Optional, Set, Callable
from datetime import datetime, date, timedelta
from decimal import Decimal
from dataclasses import dataclass, asdict
from sqlalchemy.orm import Session
from sqlalchemy import func, text, and_, or_
import redis
from contextlib import asynccontextmanager

from core.database import get_db
from core.config import settings
from ..models.analytics_models import (
    SalesAnalyticsSnapshot,
    AggregationPeriod,
    SalesMetric,
)
from modules.orders.models.order_models import Order, OrderItem
from modules.staff.models.staff_models import StaffMember

logger = logging.getLogger(__name__)


@dataclass
class RealtimeMetric:
    """Container for real-time metric data"""

    metric_name: str
    value: float
    timestamp: datetime
    change_percentage: Optional[float] = None
    previous_value: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "metric_name": self.metric_name,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "change_percentage": self.change_percentage,
            "previous_value": self.previous_value,
            "metadata": self.metadata or {},
        }


@dataclass
class DashboardSnapshot:
    """Complete dashboard metrics snapshot"""

    timestamp: datetime
    revenue_today: Decimal
    orders_today: int
    customers_today: int
    average_order_value: Decimal

    # Growth metrics
    revenue_growth: float
    order_growth: float
    customer_growth: float

    # Performance metrics
    top_staff: List[Dict[str, Any]]
    top_products: List[Dict[str, Any]]
    hourly_trends: List[Dict[str, Any]]

    # Alert indicators
    active_alerts: int
    critical_metrics: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "revenue_today": float(self.revenue_today),
            "orders_today": self.orders_today,
            "customers_today": self.customers_today,
            "average_order_value": float(self.average_order_value),
            "revenue_growth": self.revenue_growth,
            "order_growth": self.order_growth,
            "customer_growth": self.customer_growth,
            "top_staff": self.top_staff,
            "top_products": self.top_products,
            "hourly_trends": self.hourly_trends,
            "active_alerts": self.active_alerts,
            "critical_metrics": self.critical_metrics,
        }


class RealtimeMetricsService:
    """Service for managing real-time dashboard metrics with caching and streaming"""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client or self._init_redis()
        self.subscribers: Set[Callable] = set()
        self.is_running = False
        self.update_interval = 30  # Update every 30 seconds
        self.cache_ttl = 60  # Cache TTL in seconds

        self._cache_keys = {
            "dashboard_snapshot": "analytics:dashboard:snapshot",
            "hourly_metrics": "analytics:metrics:hourly",
            "daily_metrics": "analytics:metrics:daily",
            "top_performers": "analytics:performers:cache",
            "alerts_summary": "analytics:alerts:summary",
        }

    def _init_redis(self) -> Optional[redis.Redis]:
        """Initialize Redis connection"""
        try:
            redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
            client = redis.from_url(redis_url, decode_responses=True)
            # Test connection
            client.ping()
            logger.info("Redis connection established for real-time metrics")
            return client
        except Exception as e:
            logger.warning(f"Redis not available, using in-memory caching: {e}")
            return None

    async def start_realtime_updates(self):
        """Start the real-time metrics update loop"""
        if self.is_running:
            return

        self.is_running = True
        logger.info("Starting real-time metrics service")

        # Start background tasks
        update_task = asyncio.create_task(self._metrics_update_loop())
        cleanup_task = asyncio.create_task(self._cache_cleanup_loop())

        await asyncio.gather(update_task, cleanup_task, return_exceptions=True)

    async def stop_realtime_updates(self):
        """Stop the real-time metrics service"""
        self.is_running = False
        logger.info("Stopping real-time metrics service")

    def subscribe_to_updates(self, callback: Callable[[DashboardSnapshot], None]):
        """Subscribe to real-time dashboard updates"""
        self.subscribers.add(callback)
        logger.info(f"New subscriber added. Total subscribers: {len(self.subscribers)}")

    def unsubscribe_from_updates(self, callback: Callable):
        """Unsubscribe from real-time updates"""
        self.subscribers.discard(callback)
        logger.info(f"Subscriber removed. Total subscribers: {len(self.subscribers)}")

    async def get_current_dashboard_snapshot(self) -> DashboardSnapshot:
        """Get the current dashboard snapshot with caching"""

        # Try to get from cache first
        cached_snapshot = await self._get_cached_dashboard()
        if cached_snapshot:
            return cached_snapshot

        # Generate fresh snapshot
        snapshot = await self._generate_dashboard_snapshot()

        # Cache the result
        await self._cache_dashboard_snapshot(snapshot)

        return snapshot

    async def get_realtime_metric(self, metric_name: str) -> Optional[RealtimeMetric]:
        """Get a specific real-time metric"""
        try:
            db = next(get_db())

            if metric_name == "revenue_current":
                return await self._calculate_revenue_metric(db)
            elif metric_name == "orders_current":
                return await self._calculate_orders_metric(db)
            elif metric_name == "customers_current":
                return await self._calculate_customers_metric(db)
            elif metric_name == "average_order_value":
                return await self._calculate_aov_metric(db)
            else:
                # Custom metric from SalesMetric table
                return await self._get_custom_metric(db, metric_name)

        except Exception as e:
            logger.error(f"Error fetching real-time metric {metric_name}: {e}")
            return None
        finally:
            db.close()

    async def get_hourly_trends(self, hours_back: int = 24) -> List[Dict[str, Any]]:
        """Get hourly trends for the dashboard"""

        cache_key = f"{self._cache_keys['hourly_metrics']}:{hours_back}"

        # Try cache first
        if self.redis_client:
            try:
                cached_data = self.redis_client.get(cache_key)
                if cached_data:
                    return json.loads(cached_data)
            except Exception as e:
                logger.error(f"Redis cache error: {e}")

        # Generate fresh data
        trends = await self._calculate_hourly_trends(hours_back)

        # Cache the result
        if self.redis_client:
            try:
                self.redis_client.setex(
                    cache_key, 300, json.dumps(trends, default=str)  # 5 minutes cache
                )
            except Exception as e:
                logger.error(f"Redis cache set error: {e}")

        return trends

    async def get_top_performers(
        self, limit: int = 5
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get top performing staff and products"""

        cache_key = f"{self._cache_keys['top_performers']}:{limit}"

        # Try cache first
        if self.redis_client:
            try:
                cached_data = self.redis_client.get(cache_key)
                if cached_data:
                    return json.loads(cached_data)
            except Exception as e:
                logger.error(f"Redis cache error: {e}")

        # Generate fresh data
        performers = await self._calculate_top_performers(limit)

        # Cache the result
        if self.redis_client:
            try:
                self.redis_client.setex(
                    cache_key,
                    600,  # 10 minutes cache
                    json.dumps(performers, default=str),
                )
            except Exception as e:
                logger.error(f"Redis cache set error: {e}")

        return performers

    async def invalidate_cache(self, cache_pattern: Optional[str] = None):
        """Invalidate cache entries"""
        if not self.redis_client:
            return

        try:
            if cache_pattern:
                keys = self.redis_client.keys(f"analytics:*{cache_pattern}*")
                if keys:
                    self.redis_client.delete(*keys)
            else:
                # Invalidate all analytics cache
                keys = self.redis_client.keys("analytics:*")
                if keys:
                    self.redis_client.delete(*keys)

            logger.info(f"Cache invalidated for pattern: {cache_pattern or 'all'}")

        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")

    # Private methods

    async def _metrics_update_loop(self):
        """Background loop for updating metrics"""
        while self.is_running:
            try:
                # Generate new dashboard snapshot
                snapshot = await self._generate_dashboard_snapshot()

                # Cache the snapshot
                await self._cache_dashboard_snapshot(snapshot)

                # Notify all subscribers
                await self._notify_subscribers(snapshot)

                # Log metrics update
                logger.info(
                    f"Dashboard metrics updated: Revenue: ${snapshot.revenue_today}, Orders: {snapshot.orders_today}"
                )

            except Exception as e:
                logger.error(f"Error in metrics update loop: {e}")

            # Wait for next update
            await asyncio.sleep(self.update_interval)

    async def _cache_cleanup_loop(self):
        """Background loop for cache cleanup"""
        while self.is_running:
            try:
                if self.redis_client:
                    # Remove expired entries
                    expired_keys = []
                    for key in self.redis_client.keys("analytics:*"):
                        if self.redis_client.ttl(key) == -2:  # Key doesn't exist
                            expired_keys.append(key)

                    if expired_keys:
                        self.redis_client.delete(*expired_keys)
                        logger.debug(
                            f"Cleaned up {len(expired_keys)} expired cache entries"
                        )

            except Exception as e:
                logger.error(f"Error in cache cleanup: {e}")

            # Run cleanup every 5 minutes
            await asyncio.sleep(300)

    async def _generate_dashboard_snapshot(self) -> DashboardSnapshot:
        """Generate a complete dashboard metrics snapshot"""
        try:
            db = next(get_db())

            today = datetime.now().date()
            yesterday = today - timedelta(days=1)

            # Get today's metrics
            today_metrics = await self._get_daily_metrics(db, today)
            yesterday_metrics = await self._get_daily_metrics(db, yesterday)

            # Calculate growth percentages
            revenue_growth = self._calculate_growth_percentage(
                today_metrics.get("revenue", 0), yesterday_metrics.get("revenue", 0)
            )

            order_growth = self._calculate_growth_percentage(
                today_metrics.get("orders", 0), yesterday_metrics.get("orders", 0)
            )

            customer_growth = self._calculate_growth_percentage(
                today_metrics.get("customers", 0), yesterday_metrics.get("customers", 0)
            )

            # Get top performers
            top_performers = await self._calculate_top_performers(5)

            # Get hourly trends
            hourly_trends = await self._calculate_hourly_trends(12)

            # Get active alerts
            active_alerts = await self._get_active_alerts_count(db)
            critical_metrics = await self._get_critical_metrics(db)

            return DashboardSnapshot(
                timestamp=datetime.now(),
                revenue_today=Decimal(str(today_metrics.get("revenue", 0))),
                orders_today=today_metrics.get("orders", 0),
                customers_today=today_metrics.get("customers", 0),
                average_order_value=Decimal(str(today_metrics.get("aov", 0))),
                revenue_growth=revenue_growth,
                order_growth=order_growth,
                customer_growth=customer_growth,
                top_staff=top_performers.get("staff", []),
                top_products=top_performers.get("products", []),
                hourly_trends=hourly_trends,
                active_alerts=active_alerts,
                critical_metrics=critical_metrics,
            )

        except Exception as e:
            logger.error(f"Error generating dashboard snapshot: {e}")
            raise
        finally:
            db.close()

    async def _get_daily_metrics(
        self, db: Session, target_date: date
    ) -> Dict[str, Any]:
        """Get metrics for a specific date"""

        # Try to get from snapshots first
        snapshot = (
            db.query(SalesAnalyticsSnapshot)
            .filter(
                and_(
                    SalesAnalyticsSnapshot.snapshot_date == target_date,
                    SalesAnalyticsSnapshot.period_type == AggregationPeriod.DAILY,
                    SalesAnalyticsSnapshot.staff_id.is_(None),
                    SalesAnalyticsSnapshot.product_id.is_(None),
                )
            )
            .first()
        )

        if snapshot:
            return {
                "revenue": float(snapshot.total_revenue),
                "orders": snapshot.total_orders,
                "customers": snapshot.unique_customers,
                "aov": float(snapshot.average_order_value),
            }

        # Calculate from orders if no snapshot exists
        start_datetime = datetime.combine(target_date, datetime.min.time())
        end_datetime = datetime.combine(target_date, datetime.max.time())

        result = (
            db.query(
                func.coalesce(func.sum(Order.total_amount), 0).label("revenue"),
                func.count(Order.id).label("orders"),
                func.count(func.distinct(Order.customer_id)).label("customers"),
                func.coalesce(func.avg(Order.total_amount), 0).label("aov"),
            )
            .filter(
                and_(
                    Order.created_at >= start_datetime,
                    Order.created_at <= end_datetime,
                    Order.status == "completed",
                )
            )
            .first()
        )

        return {
            "revenue": float(result.revenue) if result.revenue else 0,
            "orders": result.orders if result.orders else 0,
            "customers": result.customers if result.customers else 0,
            "aov": float(result.aov) if result.aov else 0,
        }

    async def _calculate_hourly_trends(self, hours_back: int) -> List[Dict[str, Any]]:
        """Calculate hourly trends for the specified period"""
        try:
            db = next(get_db())

            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours_back)

            # Query hourly aggregated data
            hourly_data = []

            for i in range(hours_back):
                hour_start = start_time + timedelta(hours=i)
                hour_end = hour_start + timedelta(hours=1)

                result = (
                    db.query(
                        func.coalesce(func.sum(Order.total_amount), 0).label("revenue"),
                        func.count(Order.id).label("orders"),
                        func.count(func.distinct(Order.customer_id)).label("customers"),
                    )
                    .filter(
                        and_(
                            Order.created_at >= hour_start,
                            Order.created_at < hour_end,
                            Order.status == "completed",
                        )
                    )
                    .first()
                )

                hourly_data.append(
                    {
                        "hour": hour_start.strftime("%Y-%m-%d %H:00"),
                        "revenue": float(result.revenue) if result.revenue else 0,
                        "orders": result.orders if result.orders else 0,
                        "customers": result.customers if result.customers else 0,
                    }
                )

            return hourly_data

        except Exception as e:
            logger.error(f"Error calculating hourly trends: {e}")
            return []
        finally:
            db.close()

    async def _calculate_top_performers(
        self, limit: int
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Calculate top performing staff and products"""
        try:
            db = next(get_db())

            today = datetime.now().date()
            week_start = today - timedelta(days=7)

            # Top staff by revenue (last 7 days)
            top_staff_query = (
                db.query(
                    StaffMember.id,
                    StaffMember.name,
                    func.coalesce(func.sum(Order.total_amount), 0).label("revenue"),
                    func.count(Order.id).label("orders"),
                )
                .join(Order, Order.staff_id == StaffMember.id)
                .filter(
                    and_(
                        func.date(Order.created_at) >= week_start,
                        Order.status == "completed",
                    )
                )
                .group_by(StaffMember.id, StaffMember.name)
                .order_by(func.sum(Order.total_amount).desc())
                .limit(limit)
            )

            top_staff = []
            for staff in top_staff_query:
                top_staff.append(
                    {
                        "id": staff.id,
                        "name": staff.name,
                        "revenue": float(staff.revenue),
                        "orders": staff.orders,
                    }
                )

            # Top products by quantity (last 7 days)
            top_products_query = (
                db.query(
                    OrderItem.menu_item_id.label("product_id"),
                    func.sum(OrderItem.quantity).label("quantity"),
                    func.sum(OrderItem.price * OrderItem.quantity).label("revenue"),
                )
                .join(Order, Order.id == OrderItem.order_id)
                .filter(
                    and_(
                        func.date(Order.created_at) >= week_start,
                        Order.status == "completed",
                    )
                )
                .group_by(OrderItem.menu_item_id)
                .order_by(func.sum(OrderItem.quantity).desc())
                .limit(limit)
            )

            top_products = []
            for product in top_products_query:
                top_products.append(
                    {
                        "product_id": product.product_id,
                        "quantity_sold": product.quantity,
                        "revenue": float(product.revenue),
                    }
                )

            return {"staff": top_staff, "products": top_products}

        except Exception as e:
            logger.error(f"Error calculating top performers: {e}")
            return {"staff": [], "products": []}
        finally:
            db.close()

    async def _get_active_alerts_count(self, db: Session) -> int:
        """Get count of active alerts"""
        try:
            from ..models.analytics_models import AlertRule

            count = db.query(AlertRule).filter(AlertRule.is_active == True).count()
            return count
        except Exception as e:
            logger.error(f"Error getting active alerts count: {e}")
            return 0

    async def _get_critical_metrics(self, db: Session) -> List[str]:
        """Get list of critical metrics that need attention"""
        critical = []

        try:
            # Check for metrics that have dropped significantly
            today = datetime.now().date()
            yesterday = today - timedelta(days=1)

            today_metrics = await self._get_daily_metrics(db, today)
            yesterday_metrics = await self._get_daily_metrics(db, yesterday)

            # Revenue drop > 20%
            revenue_change = self._calculate_growth_percentage(
                today_metrics.get("revenue", 0), yesterday_metrics.get("revenue", 0)
            )
            if revenue_change < -20:
                critical.append("revenue_decline")

            # Order drop > 30%
            order_change = self._calculate_growth_percentage(
                today_metrics.get("orders", 0), yesterday_metrics.get("orders", 0)
            )
            if order_change < -30:
                critical.append("order_decline")

            # Customer drop > 25%
            customer_change = self._calculate_growth_percentage(
                today_metrics.get("customers", 0), yesterday_metrics.get("customers", 0)
            )
            if customer_change < -25:
                critical.append("customer_decline")

        except Exception as e:
            logger.error(f"Error identifying critical metrics: {e}")

        return critical

    def _calculate_growth_percentage(self, current: float, previous: float) -> float:
        """Calculate percentage growth between two values"""
        if previous == 0:
            return 100.0 if current > 0 else 0.0

        return ((current - previous) / previous) * 100.0

    async def _get_cached_dashboard(self) -> Optional[DashboardSnapshot]:
        """Get dashboard snapshot from cache"""
        if not self.redis_client:
            return None

        try:
            cached_data = self.redis_client.get(self._cache_keys["dashboard_snapshot"])
            if cached_data:
                data = json.loads(cached_data)
                # Reconstruct DashboardSnapshot from dict
                return DashboardSnapshot(
                    timestamp=datetime.fromisoformat(data["timestamp"]),
                    revenue_today=Decimal(str(data["revenue_today"])),
                    orders_today=data["orders_today"],
                    customers_today=data["customers_today"],
                    average_order_value=Decimal(str(data["average_order_value"])),
                    revenue_growth=data["revenue_growth"],
                    order_growth=data["order_growth"],
                    customer_growth=data["customer_growth"],
                    top_staff=data["top_staff"],
                    top_products=data["top_products"],
                    hourly_trends=data["hourly_trends"],
                    active_alerts=data["active_alerts"],
                    critical_metrics=data["critical_metrics"],
                )
        except Exception as e:
            logger.error(f"Error getting cached dashboard: {e}")

        return None

    async def _cache_dashboard_snapshot(self, snapshot: DashboardSnapshot):
        """Cache dashboard snapshot"""
        if not self.redis_client:
            return

        try:
            self.redis_client.setex(
                self._cache_keys["dashboard_snapshot"],
                self.cache_ttl,
                json.dumps(snapshot.to_dict(), default=str),
            )
        except Exception as e:
            logger.error(f"Error caching dashboard snapshot: {e}")

    async def _notify_subscribers(self, snapshot: DashboardSnapshot):
        """Notify all subscribers of new dashboard data"""
        if not self.subscribers:
            return

        # Create notification tasks
        tasks = []
        for (
            callback
        ) in self.subscribers.copy():  # Copy to avoid modification during iteration
            try:
                task = asyncio.create_task(self._safe_callback(callback, snapshot))
                tasks.append(task)
            except Exception as e:
                logger.error(f"Error creating callback task: {e}")

        # Execute all callbacks concurrently
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _safe_callback(self, callback: Callable, snapshot: DashboardSnapshot):
        """Safely execute callback with error handling"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(snapshot)
            else:
                callback(snapshot)
        except Exception as e:
            logger.error(f"Error in subscriber callback: {e}")
            # Remove problematic callback
            self.subscribers.discard(callback)

    async def _calculate_revenue_metric(self, db: Session) -> RealtimeMetric:
        """Calculate current revenue metric"""
        today = datetime.now().date()

        today_revenue = await self._get_daily_metrics(db, today)
        yesterday_revenue = await self._get_daily_metrics(db, today - timedelta(days=1))

        current_value = today_revenue.get("revenue", 0)
        previous_value = yesterday_revenue.get("revenue", 0)

        change_percentage = self._calculate_growth_percentage(
            current_value, previous_value
        )

        return RealtimeMetric(
            metric_name="revenue_current",
            value=float(current_value),
            timestamp=datetime.now(),
            change_percentage=change_percentage,
            previous_value=float(previous_value),
            metadata={"period": "daily", "currency": "USD"},
        )

    async def _calculate_orders_metric(self, db: Session) -> RealtimeMetric:
        """Calculate current orders metric"""
        today = datetime.now().date()

        today_orders = await self._get_daily_metrics(db, today)
        yesterday_orders = await self._get_daily_metrics(db, today - timedelta(days=1))

        current_value = today_orders.get("orders", 0)
        previous_value = yesterday_orders.get("orders", 0)

        change_percentage = self._calculate_growth_percentage(
            current_value, previous_value
        )

        return RealtimeMetric(
            metric_name="orders_current",
            value=float(current_value),
            timestamp=datetime.now(),
            change_percentage=change_percentage,
            previous_value=float(previous_value),
            metadata={"period": "daily"},
        )

    async def _calculate_customers_metric(self, db: Session) -> RealtimeMetric:
        """Calculate current customers metric"""
        today = datetime.now().date()

        today_customers = await self._get_daily_metrics(db, today)
        yesterday_customers = await self._get_daily_metrics(
            db, today - timedelta(days=1)
        )

        current_value = today_customers.get("customers", 0)
        previous_value = yesterday_customers.get("customers", 0)

        change_percentage = self._calculate_growth_percentage(
            current_value, previous_value
        )

        return RealtimeMetric(
            metric_name="customers_current",
            value=float(current_value),
            timestamp=datetime.now(),
            change_percentage=change_percentage,
            previous_value=float(previous_value),
            metadata={"period": "daily"},
        )

    async def _calculate_aov_metric(self, db: Session) -> RealtimeMetric:
        """Calculate current average order value metric"""
        today = datetime.now().date()

        today_aov = await self._get_daily_metrics(db, today)
        yesterday_aov = await self._get_daily_metrics(db, today - timedelta(days=1))

        current_value = today_aov.get("aov", 0)
        previous_value = yesterday_aov.get("aov", 0)

        change_percentage = self._calculate_growth_percentage(
            current_value, previous_value
        )

        return RealtimeMetric(
            metric_name="average_order_value",
            value=float(current_value),
            timestamp=datetime.now(),
            change_percentage=change_percentage,
            previous_value=float(previous_value),
            metadata={"period": "daily", "currency": "USD"},
        )

    async def _get_custom_metric(
        self, db: Session, metric_name: str
    ) -> Optional[RealtimeMetric]:
        """Get custom metric from SalesMetric table"""
        try:
            metric = (
                db.query(SalesMetric)
                .filter(SalesMetric.metric_name == metric_name)
                .order_by(SalesMetric.created_at.desc())
                .first()
            )

            if not metric:
                return None

            return RealtimeMetric(
                metric_name=metric_name,
                value=float(metric.value_numeric or metric.value_integer or 0),
                timestamp=metric.created_at,
                change_percentage=(
                    float(metric.change_percentage)
                    if metric.change_percentage
                    else None
                ),
                previous_value=(
                    float(metric.previous_value) if metric.previous_value else None
                ),
                metadata={"unit": metric.unit, "category": metric.metric_category},
            )

        except Exception as e:
            logger.error(f"Error getting custom metric {metric_name}: {e}")
            return None


# Global service instance
realtime_metrics_service = RealtimeMetricsService()


# Context manager for service lifecycle
@asynccontextmanager
async def realtime_metrics_context():
    """Context manager for managing real-time metrics service lifecycle"""
    try:
        await realtime_metrics_service.start_realtime_updates()
        yield realtime_metrics_service
    finally:
        await realtime_metrics_service.stop_realtime_updates()


# Utility functions
async def get_current_metrics() -> DashboardSnapshot:
    """Get current dashboard metrics"""
    return await realtime_metrics_service.get_current_dashboard_snapshot()


async def get_metric(metric_name: str) -> Optional[RealtimeMetric]:
    """Get a specific real-time metric"""
    return await realtime_metrics_service.get_realtime_metric(metric_name)


def subscribe_to_metrics(callback: Callable[[DashboardSnapshot], None]):
    """Subscribe to real-time metrics updates"""
    realtime_metrics_service.subscribe_to_updates(callback)


def unsubscribe_from_metrics(callback: Callable):
    """Unsubscribe from real-time metrics updates"""
    realtime_metrics_service.unsubscribe_from_updates(callback)
