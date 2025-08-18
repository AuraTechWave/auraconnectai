# backend/modules/analytics/services/background_jobs.py

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import text, func, and_

from core.database import get_db
from ..models.analytics_models import (
    SalesAnalyticsSnapshot,
    SalesMetric,
    AlertRule,
    AggregationPeriod,
)
from modules.orders.models.order_models import Order, OrderItem

logger = logging.getLogger(__name__)


class AnalyticsBackgroundJobs:
    """Background job processor for analytics tasks"""

    def __init__(self):
        self.running = False
        self.tasks = []

    async def start(self):
        """Start the background job processor"""
        self.running = True
        logger.info("Analytics background jobs started")

        # Schedule periodic tasks
        self.tasks = [
            asyncio.create_task(self._refresh_materialized_views()),
            asyncio.create_task(self._update_snapshots()),
            asyncio.create_task(self._evaluate_alerts()),
            asyncio.create_task(self._cleanup_old_data()),
        ]

        await asyncio.gather(*self.tasks, return_exceptions=True)

    async def stop(self):
        """Stop the background job processor"""
        self.running = False

        # Cancel all tasks
        for task in self.tasks:
            task.cancel()

        await asyncio.gather(*self.tasks, return_exceptions=True)
        logger.info("Analytics background jobs stopped")

    async def _refresh_materialized_views(self):
        """Refresh materialized views periodically"""
        while self.running:
            try:
                db = next(get_db())

                # Refresh top performers view
                logger.info("Refreshing materialized view: mv_top_performers")
                db.execute(
                    text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_top_performers;")
                )
                db.commit()

                # Create additional materialized views if needed
                await self._ensure_materialized_views_exist(db)

                logger.info("Materialized views refreshed successfully")

            except Exception as e:
                logger.error(f"Error refreshing materialized views: {e}")

            finally:
                db.close()

            # Refresh every 6 hours
            await asyncio.sleep(6 * 3600)

    async def _update_snapshots(self):
        """Update sales analytics snapshots"""
        while self.running:
            try:
                db = next(get_db())

                # Update snapshots for the last 3 days
                end_date = datetime.now().date()
                start_date = end_date - timedelta(days=3)

                await self._generate_daily_snapshots(db, start_date, end_date)
                await self._generate_weekly_snapshots(db)
                await self._generate_monthly_snapshots(db)

                logger.info("Sales analytics snapshots updated successfully")

            except Exception as e:
                logger.error(f"Error updating snapshots: {e}")

            finally:
                db.close()

            # Update every 2 hours
            await asyncio.sleep(2 * 3600)

    async def _evaluate_alerts(self):
        """Evaluate alert rules and trigger notifications"""
        while self.running:
            try:
                db = next(get_db())

                # Get active alert rules
                alert_rules = (
                    db.query(AlertRule).filter(AlertRule.is_active == True).all()
                )

                for rule in alert_rules:
                    await self._evaluate_single_alert(db, rule)

                logger.info(f"Evaluated {len(alert_rules)} alert rules")

            except Exception as e:
                logger.error(f"Error evaluating alerts: {e}")

            finally:
                db.close()

            # Evaluate every 15 minutes
            await asyncio.sleep(15 * 60)

    async def _cleanup_old_data(self):
        """Clean up old analytics data"""
        while self.running:
            try:
                db = next(get_db())

                # Clean up old snapshots (keep 2 years)
                cutoff_date = datetime.now().date() - timedelta(days=730)

                deleted_snapshots = (
                    db.query(SalesAnalyticsSnapshot)
                    .filter(SalesAnalyticsSnapshot.snapshot_date < cutoff_date)
                    .delete()
                )

                # Clean up old metrics (keep 1 year)
                metrics_cutoff = datetime.now().date() - timedelta(days=365)

                deleted_metrics = (
                    db.query(SalesMetric)
                    .filter(SalesMetric.metric_date < metrics_cutoff)
                    .delete()
                )

                db.commit()

                logger.info(
                    f"Cleaned up {deleted_snapshots} snapshots and {deleted_metrics} metrics"
                )

            except Exception as e:
                logger.error(f"Error cleaning up old data: {e}")

            finally:
                db.close()

            # Clean up daily at 2 AM
            await asyncio.sleep(24 * 3600)

    async def _ensure_materialized_views_exist(self, db: Session):
        """Ensure all required materialized views exist"""

        materialized_views = [
            {
                "name": "mv_top_performers",
                "query": """
                    CREATE MATERIALIZED VIEW IF NOT EXISTS mv_top_performers AS
                    SELECT 
                        DATE_TRUNC('month', snapshot_date) as month,
                        staff_id,
                        sm.name as staff_name,
                        SUM(total_revenue) as monthly_revenue,
                        SUM(total_orders) as monthly_orders,
                        AVG(average_order_value) as avg_order_value,
                        RANK() OVER (PARTITION BY DATE_TRUNC('month', snapshot_date) ORDER BY SUM(total_revenue) DESC) as revenue_rank
                    FROM sales_analytics_snapshots s
                    LEFT JOIN staff_members sm ON s.staff_id = sm.id
                    WHERE s.staff_id IS NOT NULL 
                        AND s.snapshot_date >= CURRENT_DATE - INTERVAL '12 months'
                    GROUP BY DATE_TRUNC('month', snapshot_date), staff_id, sm.name
                    ORDER BY month DESC, revenue_rank;
                """,
            },
            {
                "name": "mv_product_analytics",
                "query": """
                    CREATE MATERIALIZED VIEW IF NOT EXISTS mv_product_analytics AS
                    SELECT 
                        product_id,
                        DATE_TRUNC('week', snapshot_date) as week,
                        SUM(product_quantity_sold) as weekly_quantity,
                        SUM(product_revenue) as weekly_revenue,
                        AVG(product_revenue / NULLIF(product_quantity_sold, 0)) as avg_price,
                        RANK() OVER (PARTITION BY DATE_TRUNC('week', snapshot_date) ORDER BY SUM(product_quantity_sold) DESC) as popularity_rank
                    FROM sales_analytics_snapshots
                    WHERE product_id IS NOT NULL 
                        AND snapshot_date >= CURRENT_DATE - INTERVAL '3 months'
                    GROUP BY product_id, DATE_TRUNC('week', snapshot_date)
                    ORDER BY week DESC, popularity_rank;
                """,
            },
            {
                "name": "mv_daily_summary",
                "query": """
                    CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_summary AS
                    SELECT 
                        snapshot_date,
                        SUM(total_orders) as daily_orders,
                        SUM(total_revenue) as daily_revenue,
                        SUM(unique_customers) as daily_customers,
                        AVG(average_order_value) as daily_aov,
                        SUM(total_discounts) as daily_discounts
                    FROM sales_analytics_snapshots
                    WHERE period_type = 'daily'
                        AND snapshot_date >= CURRENT_DATE - INTERVAL '90 days'
                    GROUP BY snapshot_date
                    ORDER BY snapshot_date DESC;
                """,
            },
        ]

        for view in materialized_views:
            try:
                db.execute(text(view["query"]))

                # Create unique index for concurrent refresh
                # Use parameterized queries to prevent SQL injection
                view_name = view['name']
                
                # Validate view name to ensure it's safe
                if not view_name.replace("_", "").isalnum() or not view_name.startswith("mv_"):
                    logger.error(f"Invalid view name: {view_name}")
                    continue
                
                # Determine index columns based on query content
                if "staff_id" in view["query"]:
                    index_columns = "(month, staff_id)"
                elif "snapshot_date" in view["query"]:
                    index_columns = "(snapshot_date)"
                else:
                    index_columns = "(product_id, week)"
                
                # Build index query with validated identifiers
                index_query = f"""
                    CREATE UNIQUE INDEX IF NOT EXISTS {view_name}_unique_idx 
                    ON {view_name} {index_columns}
                """
                
                db.execute(text(index_query))
                db.commit()

                logger.info(f"Ensured materialized view exists: {view['name']}")

            except Exception as e:
                logger.error(f"Error creating materialized view {view['name']}: {e}")
                db.rollback()

    async def _generate_daily_snapshots(
        self, db: Session, start_date: date, end_date: date
    ):
        """Generate daily sales analytics snapshots"""

        current_date = start_date
        while current_date <= end_date:
            try:
                # Check if snapshot already exists
                existing = (
                    db.query(SalesAnalyticsSnapshot)
                    .filter(
                        and_(
                            SalesAnalyticsSnapshot.snapshot_date == current_date,
                            SalesAnalyticsSnapshot.period_type
                            == AggregationPeriod.DAILY,
                            SalesAnalyticsSnapshot.staff_id.is_(None),
                            SalesAnalyticsSnapshot.product_id.is_(None),
                        )
                    )
                    .first()
                )

                if existing:
                    current_date += timedelta(days=1)
                    continue

                # Calculate daily metrics from orders
                daily_metrics = (
                    db.query(
                        func.count(func.distinct(Order.id)).label("total_orders"),
                        func.coalesce(func.sum(Order.total_amount), 0).label(
                            "total_revenue"
                        ),
                        func.coalesce(func.sum(OrderItem.quantity), 0).label(
                            "total_items_sold"
                        ),
                        func.coalesce(func.avg(Order.total_amount), 0).label(
                            "average_order_value"
                        ),
                        func.coalesce(func.sum(Order.discount_amount), 0).label(
                            "total_discounts"
                        ),
                        func.coalesce(func.sum(Order.tax_amount), 0).label("total_tax"),
                        func.count(func.distinct(Order.customer_id)).label(
                            "unique_customers"
                        ),
                    )
                    .join(OrderItem)
                    .filter(
                        and_(
                            func.date(Order.created_at) == current_date,
                            Order.status == "completed",
                        )
                    )
                    .first()
                )

                if daily_metrics and daily_metrics.total_orders > 0:
                    # Create snapshot
                    snapshot = SalesAnalyticsSnapshot(
                        snapshot_date=current_date,
                        period_type=AggregationPeriod.DAILY,
                        total_orders=daily_metrics.total_orders,
                        total_revenue=Decimal(str(daily_metrics.total_revenue)),
                        total_items_sold=daily_metrics.total_items_sold,
                        average_order_value=Decimal(
                            str(daily_metrics.average_order_value)
                        ),
                        total_discounts=Decimal(str(daily_metrics.total_discounts)),
                        total_tax=Decimal(str(daily_metrics.total_tax)),
                        net_revenue=Decimal(
                            str(
                                daily_metrics.total_revenue
                                - daily_metrics.total_discounts
                            )
                        ),
                        unique_customers=daily_metrics.unique_customers,
                        calculated_at=datetime.now(),
                    )

                    db.add(snapshot)

                current_date += timedelta(days=1)

            except Exception as e:
                logger.error(f"Error generating snapshot for {current_date}: {e}")
                current_date += timedelta(days=1)

        db.commit()

    async def _generate_weekly_snapshots(self, db: Session):
        """Generate weekly aggregated snapshots"""

        # Get the start of current week
        today = datetime.now().date()
        start_of_week = today - timedelta(days=today.weekday())

        # Generate snapshots for last 4 weeks
        for week_offset in range(4):
            week_start = start_of_week - timedelta(weeks=week_offset)
            week_end = week_start + timedelta(days=6)

            # Check if weekly snapshot exists
            existing = (
                db.query(SalesAnalyticsSnapshot)
                .filter(
                    and_(
                        SalesAnalyticsSnapshot.snapshot_date == week_start,
                        SalesAnalyticsSnapshot.period_type == AggregationPeriod.WEEKLY,
                    )
                )
                .first()
            )

            if existing:
                continue

            # Aggregate daily snapshots for the week
            weekly_metrics = (
                db.query(
                    func.sum(SalesAnalyticsSnapshot.total_orders).label("total_orders"),
                    func.sum(SalesAnalyticsSnapshot.total_revenue).label(
                        "total_revenue"
                    ),
                    func.sum(SalesAnalyticsSnapshot.total_items_sold).label(
                        "total_items_sold"
                    ),
                    func.avg(SalesAnalyticsSnapshot.average_order_value).label(
                        "average_order_value"
                    ),
                    func.sum(SalesAnalyticsSnapshot.total_discounts).label(
                        "total_discounts"
                    ),
                    func.sum(SalesAnalyticsSnapshot.total_tax).label("total_tax"),
                    func.sum(SalesAnalyticsSnapshot.unique_customers).label(
                        "unique_customers"
                    ),
                )
                .filter(
                    and_(
                        SalesAnalyticsSnapshot.snapshot_date >= week_start,
                        SalesAnalyticsSnapshot.snapshot_date <= week_end,
                        SalesAnalyticsSnapshot.period_type == AggregationPeriod.DAILY,
                    )
                )
                .first()
            )

            if weekly_metrics and weekly_metrics.total_orders:
                weekly_snapshot = SalesAnalyticsSnapshot(
                    snapshot_date=week_start,
                    period_type=AggregationPeriod.WEEKLY,
                    total_orders=weekly_metrics.total_orders,
                    total_revenue=weekly_metrics.total_revenue,
                    total_items_sold=weekly_metrics.total_items_sold,
                    average_order_value=weekly_metrics.average_order_value,
                    total_discounts=weekly_metrics.total_discounts,
                    total_tax=weekly_metrics.total_tax,
                    net_revenue=weekly_metrics.total_revenue
                    - weekly_metrics.total_discounts,
                    unique_customers=weekly_metrics.unique_customers,
                    calculated_at=datetime.now(),
                )

                db.add(weekly_snapshot)

        db.commit()

    async def _generate_monthly_snapshots(self, db: Session):
        """Generate monthly aggregated snapshots"""

        # Get current month start
        today = datetime.now().date()
        month_start = today.replace(day=1)

        # Generate snapshots for last 6 months
        for month_offset in range(6):
            if month_offset == 0:
                target_month = month_start
            else:
                # Calculate previous month
                if month_start.month == 1:
                    target_month = month_start.replace(
                        year=month_start.year - 1, month=12
                    )
                else:
                    target_month = month_start.replace(
                        month=month_start.month - month_offset
                    )

            # Check if monthly snapshot exists
            existing = (
                db.query(SalesAnalyticsSnapshot)
                .filter(
                    and_(
                        SalesAnalyticsSnapshot.snapshot_date == target_month,
                        SalesAnalyticsSnapshot.period_type == AggregationPeriod.MONTHLY,
                    )
                )
                .first()
            )

            if existing:
                continue

            # Calculate month end
            if target_month.month == 12:
                month_end = target_month.replace(
                    year=target_month.year + 1, month=1
                ) - timedelta(days=1)
            else:
                month_end = target_month.replace(
                    month=target_month.month + 1
                ) - timedelta(days=1)

            # Aggregate daily snapshots for the month
            monthly_metrics = (
                db.query(
                    func.sum(SalesAnalyticsSnapshot.total_orders).label("total_orders"),
                    func.sum(SalesAnalyticsSnapshot.total_revenue).label(
                        "total_revenue"
                    ),
                    func.sum(SalesAnalyticsSnapshot.total_items_sold).label(
                        "total_items_sold"
                    ),
                    func.avg(SalesAnalyticsSnapshot.average_order_value).label(
                        "average_order_value"
                    ),
                    func.sum(SalesAnalyticsSnapshot.total_discounts).label(
                        "total_discounts"
                    ),
                    func.sum(SalesAnalyticsSnapshot.total_tax).label("total_tax"),
                    func.sum(SalesAnalyticsSnapshot.unique_customers).label(
                        "unique_customers"
                    ),
                )
                .filter(
                    and_(
                        SalesAnalyticsSnapshot.snapshot_date >= target_month,
                        SalesAnalyticsSnapshot.snapshot_date <= month_end,
                        SalesAnalyticsSnapshot.period_type == AggregationPeriod.DAILY,
                    )
                )
                .first()
            )

            if monthly_metrics and monthly_metrics.total_orders:
                monthly_snapshot = SalesAnalyticsSnapshot(
                    snapshot_date=target_month,
                    period_type=AggregationPeriod.MONTHLY,
                    total_orders=monthly_metrics.total_orders,
                    total_revenue=monthly_metrics.total_revenue,
                    total_items_sold=monthly_metrics.total_items_sold,
                    average_order_value=monthly_metrics.average_order_value,
                    total_discounts=monthly_metrics.total_discounts,
                    total_tax=monthly_metrics.total_tax,
                    net_revenue=monthly_metrics.total_revenue
                    - monthly_metrics.total_discounts,
                    unique_customers=monthly_metrics.unique_customers,
                    calculated_at=datetime.now(),
                )

                db.add(monthly_snapshot)

        db.commit()

    async def _evaluate_single_alert(self, db: Session, rule: AlertRule):
        """Evaluate a single alert rule"""

        try:
            # Get current metric value
            current_value = self._get_metric_value(
                db, rule.metric_name, rule.evaluation_period
            )

            if current_value is None:
                return

            # Get comparison value if needed
            comparison_value = None
            if rule.comparison_period:
                comparison_value = self._get_comparison_value(
                    db, rule.metric_name, rule.comparison_period
                )

            # Evaluate condition
            should_trigger = self._evaluate_alert_condition(
                rule, current_value, comparison_value
            )

            if should_trigger:
                # Check if we should throttle (don't trigger too frequently)
                if self._should_throttle_alert(rule):
                    return

                # Trigger alert
                await self._trigger_alert(db, rule, current_value, comparison_value)

                # Update rule statistics
                rule.last_triggered_at = datetime.now()
                rule.trigger_count += 1
                db.commit()

                logger.info(f"Alert triggered: {rule.name} (value: {current_value})")

        except Exception as e:
            logger.error(f"Error evaluating alert rule {rule.name}: {e}")

    def _get_metric_value(
        self, db: Session, metric_name: str, period: str
    ) -> Optional[float]:
        """Get current metric value"""

        # This would implement metric value retrieval
        # For now, return a placeholder
        return 100.0

    def _get_comparison_value(
        self, db: Session, metric_name: str, comparison_period: str
    ) -> Optional[float]:
        """Get comparison metric value"""

        # This would implement comparison value retrieval
        return 95.0

    def _evaluate_alert_condition(
        self, rule: AlertRule, current_value: float, comparison_value: Optional[float]
    ) -> bool:
        """Evaluate if alert condition is met"""

        if rule.condition_type == "above":
            return current_value > float(rule.threshold_value)
        elif rule.condition_type == "below":
            return current_value < float(rule.threshold_value)
        elif rule.condition_type == "change" and comparison_value:
            change_percentage = (
                (current_value - comparison_value) / comparison_value
            ) * 100
            return abs(change_percentage) > float(rule.threshold_value)

        return False

    def _should_throttle_alert(self, rule: AlertRule) -> bool:
        """Check if alert should be throttled"""

        if not rule.last_triggered_at:
            return False

        # Don't trigger more than once per hour
        time_since_last = datetime.now() - rule.last_triggered_at
        return time_since_last.total_seconds() < 3600

    async def _trigger_alert(
        self,
        db: Session,
        rule: AlertRule,
        current_value: float,
        comparison_value: Optional[float],
    ):
        """Trigger alert notification"""

        # This would implement actual alert notifications
        # (email, Slack, webhook, etc.)
        logger.warning(
            f"ALERT: {rule.name} - Current value: {current_value}, Threshold: {rule.threshold_value}"
        )


# Global instance
background_jobs = AnalyticsBackgroundJobs()


# Utility functions for manual job execution
async def refresh_all_materialized_views():
    """Manually refresh all materialized views"""
    db = next(get_db())
    try:
        views = ["mv_top_performers", "mv_product_analytics", "mv_daily_summary"]

        for view in views:
            db.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view};"))
            logger.info(f"Refreshed materialized view: {view}")

        db.commit()

    except Exception as e:
        logger.error(f"Error refreshing materialized views: {e}")
        db.rollback()
    finally:
        db.close()


async def generate_snapshots_for_date_range(start_date: date, end_date: date):
    """Manually generate snapshots for a date range"""
    db = next(get_db())
    try:
        jobs = AnalyticsBackgroundJobs()
        await jobs._generate_daily_snapshots(db, start_date, end_date)
        logger.info(f"Generated snapshots for {start_date} to {end_date}")

    except Exception as e:
        logger.error(f"Error generating snapshots: {e}")
    finally:
        db.close()
