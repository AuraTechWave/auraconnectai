# backend/modules/orders/tasks/pricing_rule_tasks.py

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.database_utils import get_db_context as get_async_db
from ..models.pricing_rule_models import PricingRule, RuleStatus, PricingRuleMetrics
from ..metrics.pricing_rule_metrics import pricing_metrics_collector

logger = logging.getLogger(__name__)


class PricingRuleMaintenanceWorker:
    """Background worker for pricing rule maintenance tasks"""

    def __init__(self):
        self.running = False
        self.tasks = []

    async def start(self):
        """Start the background worker"""
        if self.running:
            logger.warning("Pricing rule worker already running")
            return

        self.running = True
        logger.info("Starting pricing rule maintenance worker")

        # Schedule tasks
        self.tasks = [
            asyncio.create_task(
                self._run_periodic_task(
                    self.expire_rules_task,
                    interval_minutes=60,  # Run hourly
                    task_name="expire_rules",
                )
            ),
            asyncio.create_task(
                self._run_periodic_task(
                    self.update_metrics_gauges_task,
                    interval_minutes=5,  # Run every 5 minutes
                    task_name="update_metrics",
                )
            ),
            asyncio.create_task(
                self._run_periodic_task(
                    self.cleanup_old_metrics_task,
                    interval_minutes=1440,  # Run daily
                    task_name="cleanup_metrics",
                )
            ),
        ]

    async def stop(self):
        """Stop the background worker"""
        self.running = False

        # Cancel all tasks
        for task in self.tasks:
            task.cancel()

        # Wait for tasks to complete
        await asyncio.gather(*self.tasks, return_exceptions=True)

        logger.info("Pricing rule maintenance worker stopped")

    async def _run_periodic_task(
        self, task_func, interval_minutes: int, task_name: str
    ):
        """Run a task periodically"""
        interval_seconds = interval_minutes * 60

        while self.running:
            try:
                logger.debug(f"Running {task_name} task")
                await task_func()
                logger.debug(f"Completed {task_name} task")
            except Exception as e:
                logger.error(f"Error in {task_name} task: {str(e)}")

            # Wait for next interval
            await asyncio.sleep(interval_seconds)

    async def expire_rules_task(self):
        """Check and expire rules that have passed their valid_until date"""

        async with get_async_db() as db:
            try:
                # Find rules that should be expired
                result = await db.execute(
                    select(PricingRule).where(
                        and_(
                            PricingRule.status == RuleStatus.ACTIVE,
                            PricingRule.valid_until.isnot(None),
                            PricingRule.valid_until < datetime.utcnow(),
                        )
                    )
                )

                expired_rules = result.scalars().all()

                if expired_rules:
                    logger.info(f"Found {len(expired_rules)} rules to expire")

                    # Update status to expired
                    for rule in expired_rules:
                        rule.status = RuleStatus.EXPIRED
                        logger.info(
                            f"Expired rule {rule.rule_id} ({rule.name}) - "
                            f"valid_until: {rule.valid_until}"
                        )

                    await db.commit()

                    # Update metrics by restaurant
                    restaurant_counts = {}
                    for rule in expired_rules:
                        if rule.restaurant_id not in restaurant_counts:
                            restaurant_counts[rule.restaurant_id] = 0
                        restaurant_counts[rule.restaurant_id] += 1

                    # Record expiry metrics
                    for restaurant_id, count in restaurant_counts.items():
                        pricing_metrics_collector.record_rule_skipped(
                            restaurant_id, f"expired_{count}_rules"
                        )

            except Exception as e:
                logger.error(f"Error expiring rules: {str(e)}")
                await db.rollback()

    async def update_metrics_gauges_task(self):
        """Update Prometheus gauge metrics"""

        async with get_async_db() as db:
            try:
                # Get active rule counts by restaurant and type
                result = await db.execute(
                    select(
                        PricingRule.restaurant_id,
                        PricingRule.rule_type,
                        func.count(PricingRule.id).label("count"),
                    )
                    .where(PricingRule.status == RuleStatus.ACTIVE)
                    .group_by(PricingRule.restaurant_id, PricingRule.rule_type)
                )

                # Group by restaurant
                restaurant_rules: Dict[int, Dict[str, int]] = {}
                for row in result:
                    restaurant_id = row.restaurant_id
                    rule_type = row.rule_type.value
                    count = row.count

                    if restaurant_id not in restaurant_rules:
                        restaurant_rules[restaurant_id] = {}

                    restaurant_rules[restaurant_id][rule_type] = count

                # Update gauges
                for restaurant_id, rule_counts in restaurant_rules.items():
                    pricing_metrics_collector.update_active_rules_gauge(
                        restaurant_id, rule_counts
                    )

                # Get today's discount totals
                today_start = datetime.utcnow().replace(
                    hour=0, minute=0, second=0, microsecond=0
                )

                result = await db.execute(
                    select(
                        PricingRuleMetrics.rule_id,
                        PricingRule.restaurant_id,
                        func.sum(PricingRuleMetrics.total_discount_amount).label(
                            "total_discount"
                        ),
                    )
                    .join(PricingRule, PricingRule.id == PricingRuleMetrics.rule_id)
                    .where(PricingRuleMetrics.date >= today_start)
                    .group_by(PricingRuleMetrics.rule_id, PricingRule.restaurant_id)
                )

                # Sum by restaurant
                restaurant_discounts: Dict[int, float] = {}
                for row in result:
                    restaurant_id = row.restaurant_id
                    discount = float(row.total_discount or 0)

                    if restaurant_id not in restaurant_discounts:
                        restaurant_discounts[restaurant_id] = 0

                    restaurant_discounts[restaurant_id] += discount

                # Update discount gauges
                for restaurant_id, total_discount in restaurant_discounts.items():
                    pricing_metrics_collector.update_daily_discount_gauge(
                        restaurant_id, total_discount
                    )

            except Exception as e:
                logger.error(f"Error updating metrics gauges: {str(e)}")

    async def cleanup_old_metrics_task(self):
        """Clean up old metrics data"""

        async with get_async_db() as db:
            try:
                # Keep only last 90 days of metrics
                cutoff_date = datetime.utcnow() - timedelta(days=90)

                result = await db.execute(
                    select(func.count(PricingRuleMetrics.id)).where(
                        PricingRuleMetrics.date < cutoff_date
                    )
                )

                old_count = result.scalar()

                if old_count > 0:
                    logger.info(f"Cleaning up {old_count} old metric records")

                    # Delete old records
                    await db.execute(
                        PricingRuleMetrics.__table__.delete().where(
                            PricingRuleMetrics.date < cutoff_date
                        )
                    )

                    await db.commit()
                    logger.info(f"Cleaned up {old_count} old metric records")

            except Exception as e:
                logger.error(f"Error cleaning up metrics: {str(e)}")
                await db.rollback()


# Create singleton worker instance
pricing_rule_worker = PricingRuleMaintenanceWorker()


# Helper functions for integration


async def start_pricing_rule_worker():
    """Start the pricing rule maintenance worker"""
    await pricing_rule_worker.start()


async def stop_pricing_rule_worker():
    """Stop the pricing rule maintenance worker"""
    await pricing_rule_worker.stop()


# Manual task triggers (for testing or admin use)


async def manually_expire_rules():
    """Manually trigger rule expiration check"""
    worker = PricingRuleMaintenanceWorker()
    await worker.expire_rules_task()


async def manually_update_metrics():
    """Manually trigger metrics update"""
    worker = PricingRuleMaintenanceWorker()
    await worker.update_metrics_gauges_task()


async def manually_cleanup_metrics():
    """Manually trigger metrics cleanup"""
    worker = PricingRuleMaintenanceWorker()
    await worker.cleanup_old_metrics_task()
