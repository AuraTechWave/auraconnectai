# backend/modules/promotions/services/analytics_task_service.py

from sqlalchemy.orm import Session
from typing import Dict, Any, List
from datetime import datetime, timedelta
import logging
import asyncio

from core.database import get_db
from .analytics_service import PromotionAnalyticsService
from .reporting_service import PromotionReportingService
from ..models.promotion_models import PromotionAnalytics

logger = logging.getLogger(__name__)


class AnalyticsTaskService:
    """Service for handling automated analytics tasks and data aggregation"""

    def __init__(self):
        self.analytics_service = None
        self.reporting_service = None

    def _get_services(self, db: Session):
        """Initialize services with database session"""
        if not self.analytics_service:
            self.analytics_service = PromotionAnalyticsService(db)
        if not self.reporting_service:
            self.reporting_service = PromotionReportingService(db)
        return self.analytics_service, self.reporting_service

    async def run_daily_analytics_aggregation(
        self, target_date: datetime = None
    ) -> Dict[str, Any]:
        """
        Run daily analytics aggregation task

        Args:
            target_date: Date to aggregate (defaults to yesterday)

        Returns:
            Dictionary with aggregation results
        """
        try:
            if not target_date:
                target_date = datetime.utcnow() - timedelta(days=1)

            # Get database session
            db = next(get_db())
            analytics_service, _ = self._get_services(db)

            # Generate daily aggregates
            aggregates = analytics_service.generate_daily_analytics_aggregates(
                target_date
            )

            # Store aggregates in database
            storage_results = await self._store_daily_aggregates(
                db, aggregates, target_date
            )

            logger.info(
                f"Completed daily analytics aggregation for {target_date.date()}"
            )

            return {
                "target_date": target_date.date().isoformat(),
                "aggregates_generated": True,
                "storage_results": storage_results,
                "completed_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error in daily analytics aggregation: {str(e)}")
            return {
                "target_date": target_date.date().isoformat() if target_date else None,
                "aggregates_generated": False,
                "error": str(e),
                "completed_at": datetime.utcnow().isoformat(),
            }
        finally:
            if "db" in locals():
                db.close()

    async def _store_daily_aggregates(
        self, db: Session, aggregates: Dict[str, Any], target_date: datetime
    ) -> Dict[str, Any]:
        """Store daily aggregates in the database"""

        try:
            stored_records = 0

            # Store promotion aggregates
            for promo_agg in aggregates.get("promotion_aggregates", []):
                # Check if record already exists
                existing = (
                    db.query(PromotionAnalytics)
                    .filter(
                        PromotionAnalytics.promotion_id == promo_agg["promotion_id"],
                        PromotionAnalytics.date == target_date.date(),
                        PromotionAnalytics.period_type == "daily",
                    )
                    .first()
                )

                if existing:
                    # Update existing record
                    existing.impressions = promo_agg.get("impressions", 0)
                    existing.clicks = promo_agg.get("clicks", 0)
                    existing.conversions = promo_agg["usage_count"]
                    existing.revenue = promo_agg["total_revenue"]
                    existing.discount_amount = promo_agg["total_discount"]
                    existing.unique_customers = promo_agg["unique_customers"]
                    existing.conversion_rate = (
                        promo_agg["usage_count"]
                        / max(promo_agg.get("impressions", 1), 1)
                        * 100
                    )
                    existing.average_order_value = promo_agg["total_revenue"] / max(
                        promo_agg["usage_count"], 1
                    )

                    if promo_agg["total_discount"] > 0:
                        existing.return_on_investment = (
                            (promo_agg["total_revenue"] - promo_agg["total_discount"])
                            / promo_agg["total_discount"]
                        ) * 100

                else:
                    # Create new record
                    analytics_record = PromotionAnalytics(
                        promotion_id=promo_agg["promotion_id"],
                        date=target_date.date(),
                        period_type="daily",
                        impressions=promo_agg.get("impressions", 0),
                        clicks=promo_agg.get("clicks", 0),
                        conversions=promo_agg["usage_count"],
                        revenue=promo_agg["total_revenue"],
                        discount_amount=promo_agg["total_discount"],
                        unique_customers=promo_agg["unique_customers"],
                        conversion_rate=promo_agg["usage_count"]
                        / max(promo_agg.get("impressions", 1), 1)
                        * 100,
                        average_order_value=promo_agg["total_revenue"]
                        / max(promo_agg["usage_count"], 1),
                        customer_acquisition_cost=0.0,  # Would need marketing spend data
                        return_on_investment=(
                            (
                                (
                                    promo_agg["total_revenue"]
                                    - promo_agg["total_discount"]
                                )
                                / promo_agg["total_discount"]
                            )
                            * 100
                            if promo_agg["total_discount"] > 0
                            else 0
                        ),
                    )
                    db.add(analytics_record)

                stored_records += 1

            db.commit()

            return {
                "promotion_records_stored": stored_records,
                "coupon_aggregates_stored": bool(aggregates.get("coupon_aggregates")),
                "referral_aggregates_stored": bool(
                    aggregates.get("referral_aggregates")
                ),
            }

        except Exception as e:
            db.rollback()
            logger.error(f"Error storing daily aggregates: {str(e)}")
            raise

    async def generate_weekly_reports(self) -> Dict[str, Any]:
        """Generate and process weekly reports"""

        try:
            db = next(get_db())
            _, reporting_service = self._get_services(db)

            # Generate weekly executive summary
            executive_report = reporting_service.generate_scheduled_report(
                report_type="executive", frequency="weekly"
            )

            # Generate weekly performance report
            performance_report = reporting_service.generate_scheduled_report(
                report_type="performance", frequency="weekly"
            )

            # You could send these reports via email here
            # await self._send_weekly_reports(executive_report, performance_report)

            logger.info("Generated weekly reports successfully")

            return {
                "executive_report_generated": True,
                "performance_report_generated": True,
                "reports_sent": False,  # Would be True if email sending is implemented
                "generated_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error generating weekly reports: {str(e)}")
            return {
                "executive_report_generated": False,
                "performance_report_generated": False,
                "error": str(e),
                "generated_at": datetime.utcnow().isoformat(),
            }
        finally:
            if "db" in locals():
                db.close()

    async def cleanup_old_analytics_data(
        self, retention_days: int = 365
    ) -> Dict[str, Any]:
        """
        Clean up old analytics data beyond retention period

        Args:
            retention_days: Number of days to retain data

        Returns:
            Dictionary with cleanup results
        """
        try:
            db = next(get_db())

            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

            # Delete old analytics records
            deleted_count = (
                db.query(PromotionAnalytics)
                .filter(PromotionAnalytics.date < cutoff_date.date())
                .delete()
            )

            db.commit()

            logger.info(f"Cleaned up {deleted_count} old analytics records")

            return {
                "records_deleted": deleted_count,
                "cutoff_date": cutoff_date.date().isoformat(),
                "retention_days": retention_days,
                "completed_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error cleaning up analytics data: {str(e)}")
            return {
                "records_deleted": 0,
                "error": str(e),
                "completed_at": datetime.utcnow().isoformat(),
            }
        finally:
            if "db" in locals():
                db.close()

    async def update_promotion_performance_metrics(self) -> Dict[str, Any]:
        """Update real-time promotion performance metrics"""

        try:
            db = next(get_db())

            from ..models.promotion_models import (
                Promotion,
                PromotionUsage,
                PromotionStatus,
            )
            from sqlalchemy import func

            # Get all active promotions
            active_promotions = (
                db.query(Promotion)
                .filter(Promotion.status == PromotionStatus.ACTIVE)
                .all()
            )

            updated_count = 0

            for promotion in active_promotions:
                # Calculate current metrics
                usage_data = (
                    db.query(
                        func.count(PromotionUsage.id).label("total_usage"),
                        func.sum(PromotionUsage.final_order_amount).label(
                            "total_revenue"
                        ),
                        func.count(func.distinct(PromotionUsage.customer_id)).label(
                            "unique_customers"
                        ),
                    )
                    .filter(PromotionUsage.promotion_id == promotion.id)
                    .first()
                )

                # Update promotion metrics
                if usage_data and usage_data.total_usage:
                    promotion.current_uses = usage_data.total_usage
                    promotion.revenue_generated = float(usage_data.total_revenue or 0)
                    promotion.conversions = usage_data.total_usage

                    # Calculate conversion rate if impressions are available
                    if promotion.impressions > 0:
                        promotion.conversion_rate = (
                            usage_data.total_usage / promotion.impressions
                        ) * 100

                    updated_count += 1

            db.commit()

            logger.info(f"Updated performance metrics for {updated_count} promotions")

            return {
                "promotions_updated": updated_count,
                "total_active_promotions": len(active_promotions),
                "updated_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error updating promotion performance metrics: {str(e)}")
            return {
                "promotions_updated": 0,
                "error": str(e),
                "updated_at": datetime.utcnow().isoformat(),
            }
        finally:
            if "db" in locals():
                db.close()

    async def detect_promotion_anomalies(self) -> Dict[str, Any]:
        """Detect anomalies in promotion performance"""

        try:
            db = next(get_db())
            analytics_service, _ = self._get_services(db)

            # Get recent performance data
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=7)

            performance_report = (
                analytics_service.generate_promotion_performance_report(
                    start_date=start_date, end_date=end_date
                )
            )

            anomalies = []

            # Check for performance anomalies
            for promo in performance_report["promotion_details"]:
                # Check for unusually low conversion rates
                conversion_rate = promo["engagement_metrics"][
                    "conversion_rate_percentage"
                ]
                if (
                    conversion_rate < 1.0
                    and promo["engagement_metrics"]["impressions"] > 100
                ):
                    anomalies.append(
                        {
                            "promotion_id": promo["promotion_id"],
                            "promotion_name": promo["promotion_name"],
                            "anomaly_type": "low_conversion_rate",
                            "value": conversion_rate,
                            "threshold": 1.0,
                            "severity": "medium",
                        }
                    )

                # Check for unusually low ROI
                roi = promo["financial_metrics"]["roi_percentage"]
                if roi < 50 and promo["usage_metrics"]["total_usage"] > 10:
                    anomalies.append(
                        {
                            "promotion_id": promo["promotion_id"],
                            "promotion_name": promo["promotion_name"],
                            "anomaly_type": "low_roi",
                            "value": roi,
                            "threshold": 50,
                            "severity": "high",
                        }
                    )

                # Check for no usage despite impressions
                if (
                    promo["usage_metrics"]["total_usage"] == 0
                    and promo["engagement_metrics"]["impressions"] > 50
                ):
                    anomalies.append(
                        {
                            "promotion_id": promo["promotion_id"],
                            "promotion_name": promo["promotion_name"],
                            "anomaly_type": "no_usage_with_impressions",
                            "value": 0,
                            "threshold": 1,
                            "severity": "high",
                        }
                    )

            logger.info(f"Detected {len(anomalies)} promotion anomalies")

            return {
                "anomalies_detected": len(anomalies),
                "anomalies": anomalies,
                "analysis_period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                },
                "analyzed_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error detecting promotion anomalies: {str(e)}")
            return {
                "anomalies_detected": 0,
                "error": str(e),
                "analyzed_at": datetime.utcnow().isoformat(),
            }
        finally:
            if "db" in locals():
                db.close()


# Singleton instance for background tasks
analytics_task_service = AnalyticsTaskService()


# Background task functions that can be called by task schedulers
async def daily_analytics_task():
    """Daily analytics aggregation task"""
    return await analytics_task_service.run_daily_analytics_aggregation()


async def weekly_reports_task():
    """Weekly reports generation task"""
    return await analytics_task_service.generate_weekly_reports()


async def performance_metrics_update_task():
    """Performance metrics update task"""
    return await analytics_task_service.update_promotion_performance_metrics()


async def anomaly_detection_task():
    """Anomaly detection task"""
    return await analytics_task_service.detect_promotion_anomalies()


async def cleanup_analytics_task():
    """Analytics data cleanup task"""
    return await analytics_task_service.cleanup_old_analytics_data()
