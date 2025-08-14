"""backend/workers/data_retention_worker.py

Background worker that enforces data-retention policies across multiple
modules.  The job runs on Arq and executes individual cleanup tasks that
are already implemented inside each domain service.  Retention periods are
fully configurable via environment variables – no code-changes are required
for ops teams to tweak policies.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any
from contextlib import closing

from arq import cron
from arq.connections import RedisSettings

from core.session_manager import SessionManager
from core.database import get_db

# Optional dependencies.  Import lazily so the worker still starts when a
# given module is disabled / not installed.
try:
    from modules.staff.services.biometric_service import BiometricService
except Exception:  # pragma: no cover – best-effort import
    BiometricService = None  # type: ignore

try:
    from modules.promotions.services.analytics_task_service import (
        AnalyticsTaskService,
    )
except Exception:  # pragma: no cover
    AnalyticsTaskService = None  # type: ignore


logger = logging.getLogger(__name__)


class DataRetentionWorker:  # pylint: disable=too-few-public-methods
    """Collection of async tasks used by Arq for periodic data clean-up."""

    # ---------------------------------------------------------------------
    # Session & token clean-up
    # ---------------------------------------------------------------------
    @staticmethod
    async def cleanup_expired_sessions(ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Remove expired auth sessions and black-listed tokens."""

        start = datetime.utcnow()
        manager = SessionManager()
        cleaned_count = manager.cleanup_expired_sessions()

        logger.info("Cleaned up %s expired sessions", cleaned_count)
        return {
            "task": "cleanup_expired_sessions",
            "cleaned": cleaned_count,
            "duration_ms": int((datetime.utcnow() - start).total_seconds() * 1000),
        }

    # ------------------------------------------------------------------
    # Biometric data clean-up
    # ------------------------------------------------------------------
    @staticmethod
    async def cleanup_biometric_data(ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Apply GDPR retention rules to biometric templates & audit logs."""

        if BiometricService is None:
            logger.warning("BiometricService not available – skipping")
            return {"task": "cleanup_biometric_data", "skipped": True}

        start = datetime.utcnow()

        # Run synchronous database operations in async context
        # Use a helper to properly exhaust the generator and ensure cleanup
        biometric_cnt = 0
        audit_cnt = 0
        
        # Create a helper function to properly use the generator
        def run_cleanup():
            nonlocal biometric_cnt, audit_cnt
            # This will properly iterate through the generator ensuring finally block runs
            for db in get_db():
                service = BiometricService(db)  # type: ignore[call-arg]
                biometric_cnt, audit_cnt = service.cleanup_expired_data()
                break  # Only need one iteration
        
        # Run the synchronous operation
        run_cleanup()

        logger.info(
            "Removed %s biometric records and %s audit entries", biometric_cnt, audit_cnt
        )
        return {
            "task": "cleanup_biometric_data",
            "biometrics_deleted": biometric_cnt,
            "audit_deleted": audit_cnt,
            "duration_ms": int((datetime.utcnow() - start).total_seconds() * 1000),
        }

    # ------------------------------------------------------------------
    # Analytics retention clean-up
    # ------------------------------------------------------------------
    @staticmethod
    async def cleanup_analytics(ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Purge outdated promotion analytics based on retention settings."""

        if AnalyticsTaskService is None:
            logger.warning("AnalyticsTaskService not available – skipping")
            return {"task": "cleanup_analytics", "skipped": True}

        start = datetime.utcnow()

        from core.config_validation import config
        retention_days = config.ANALYTICS_RETENTION_DAYS
        service: AnalyticsTaskService = AnalyticsTaskService()  # type: ignore[valid-type]
        # The service method is *async* so we await it here.
        result = await service.cleanup_old_analytics_data(retention_days=retention_days)  # type: ignore[arg-type]

        result.update(
            {
                "task": "cleanup_analytics",
                "duration_ms": int((datetime.utcnow() - start).total_seconds() * 1000),
            }
        )
        return result


# -------------------------------------------------------------------------
# Arq worker configuration
# -------------------------------------------------------------------------


async def startup(ctx: Dict[str, Any]):
    logger.info("Data-retention worker starting up")
    ctx["startup_time"] = datetime.utcnow()


async def shutdown(ctx: Dict[str, Any]):
    logger.info("Data-retention worker shutting down")


# Worker settings consumed by arq.run_worker
WorkerSettings = {
    "redis_settings": RedisSettings.from_dsn(os.getenv("REDIS_URL", "redis://localhost:6379")),
    "max_jobs": 10,
    "job_timeout": 300,
    "keep_result": 3600,  # 1h
    "functions": [
        DataRetentionWorker.cleanup_expired_sessions,
        DataRetentionWorker.cleanup_biometric_data,
        DataRetentionWorker.cleanup_analytics,
    ],
    "cron_jobs": [
        # Daily maintenance window at 03:15 UTC
        cron(DataRetentionWorker.cleanup_expired_sessions, hour=3, minute=15),
        cron(DataRetentionWorker.cleanup_biometric_data, hour=3, minute=20),
        cron(DataRetentionWorker.cleanup_analytics, hour=3, minute=25),
    ],
    "on_startup": startup,
    "on_shutdown": shutdown,
}


if __name__ == "__main__":
    from arq import run_worker

    run_worker(WorkerSettings)