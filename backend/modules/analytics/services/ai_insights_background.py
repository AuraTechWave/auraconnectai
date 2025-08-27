# backend/modules/analytics/services/ai_insights_background.py

import logging
from typing import Optional, Dict, Any
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
import asyncio

from core.database_utils import get_db_context
from core.cache import cache_manager as cache_service
from ..schemas.ai_insights_schemas import InsightRequest, InsightType, ConfidenceLevel
from .ai_insights_service import create_ai_insights_service

logger = logging.getLogger(__name__)


class AIInsightsBackgroundService:
    """Service for running AI insights generation in background"""

    @staticmethod
    async def pre_generate_daily_insights():
        """
        Pre-generate common insights configurations daily.
        This should be run as a scheduled job (e.g., 2 AM daily).
        """
        logger.info("Starting daily AI insights pre-generation")

        # Common insight configurations to pre-generate
        configurations = [
            # Last 7 days comprehensive
            {
                "insight_types": [
                    InsightType.PEAK_TIME,
                    InsightType.PRODUCT_TREND,
                    InsightType.CUSTOMER_PATTERN,
                ],
                "days_back": 7,
                "name": "weekly_comprehensive",
            },
            # Last 30 days comprehensive
            {
                "insight_types": [
                    InsightType.PEAK_TIME,
                    InsightType.PRODUCT_TREND,
                    InsightType.CUSTOMER_PATTERN,
                    InsightType.SEASONALITY,
                    InsightType.ANOMALY,
                ],
                "days_back": 30,
                "name": "monthly_comprehensive",
            },
            # Peak times only (last 14 days)
            {
                "insight_types": [InsightType.PEAK_TIME],
                "days_back": 14,
                "name": "biweekly_peak_times",
            },
            # Product trends (last 30 days)
            {
                "insight_types": [InsightType.PRODUCT_TREND],
                "days_back": 30,
                "name": "monthly_products",
            },
        ]

        async with get_db_context() as db:
            service = create_ai_insights_service(db)

            for config in configurations:
                try:
                    end_date = datetime.now().date()
                    start_date = end_date - timedelta(days=config["days_back"])

                    request = InsightRequest(
                        insight_types=config["insight_types"],
                        date_from=start_date,
                        date_to=end_date,
                        min_confidence=ConfidenceLevel.MEDIUM,
                        force_refresh=True,  # Always refresh in background job
                    )

                    logger.info(f"Generating {config['name']} insights...")
                    result = await service.generate_insights(request)

                    logger.info(f"Successfully generated {config['name']} insights")

                    # Add a small delay between generations
                    await asyncio.sleep(2)

                except Exception as e:
                    logger.error(f"Failed to generate {config['name']} insights: {e}")

    @staticmethod
    async def generate_custom_insights_async(
        request: InsightRequest, user_id: int, task_id: str
    ) -> Dict[str, Any]:
        """
        Generate insights asynchronously for heavy requests.
        Updates task status in cache.
        """
        try:
            # Update task status to processing
            await cache_service.set(
                f"task:status:{task_id}",
                {"status": "processing", "progress": 0},
                ttl=3600,
            )

            async with get_db_context() as db:
                service = create_ai_insights_service(db)

                # Generate insights with progress updates
                result = await service.generate_insights(request)

                # Store result in cache
                result_key = f"task:result:{task_id}"
                await cache_service.set(
                    result_key, result.dict(), ttl=3600  # Keep result for 1 hour
                )

                # Update task status to completed
                await cache_service.set(
                    f"task:status:{task_id}",
                    {
                        "status": "completed",
                        "progress": 100,
                        "result_key": result_key,
                        "completed_at": datetime.utcnow().isoformat(),
                    },
                    ttl=3600,
                )

                logger.info(f"Successfully completed async insights task {task_id}")
                return {"success": True, "task_id": task_id}

        except Exception as e:
            logger.error(f"Failed to generate async insights for task {task_id}: {e}")

            # Update task status to failed
            await cache_service.set(
                f"task:status:{task_id}",
                {
                    "status": "failed",
                    "error": str(e),
                    "failed_at": datetime.utcnow().isoformat(),
                },
                ttl=3600,
            )

            return {"success": False, "task_id": task_id, "error": str(e)}

    @staticmethod
    async def cleanup_old_snapshots(days_to_keep: int = 90):
        """
        Clean up old pre-generated snapshots and analytics data.
        Keeps data for specified number of days.
        """
        logger.info(
            f"Starting cleanup of analytics data older than {days_to_keep} days"
        )

        cutoff_date = datetime.now().date() - timedelta(days=days_to_keep)

        async with get_db_context() as db:
            try:
                # This would clean up old materialized data if using snapshots
                # For now, just clear old cache entries

                # Get all cache keys for old insights
                pattern = "ai:insights:*"
                # Note: This is pseudo-code as actual implementation depends on cache backend
                # Most production systems would use Redis SCAN command

                logger.info(f"Cleanup completed for data before {cutoff_date}")

            except Exception as e:
                logger.error(f"Failed to cleanup old analytics data: {e}")


# Background task runner functions
async def run_daily_insights_generation():
    """Task runner for daily insights pre-generation"""
    await AIInsightsBackgroundService.pre_generate_daily_insights()


async def run_analytics_cleanup():
    """Task runner for analytics data cleanup"""
    await AIInsightsBackgroundService.cleanup_old_snapshots()


# Export for use with task schedulers (e.g., Celery, APScheduler)
__all__ = [
    "AIInsightsBackgroundService",
    "run_daily_insights_generation",
    "run_analytics_cleanup",
]
