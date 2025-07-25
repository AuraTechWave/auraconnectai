import logging
from typing import Optional
from sqlalchemy.orm import Session
from .order_service import cancel_stale_orders

logger = logging.getLogger(__name__)


class AutoCancellationScheduler:
    """Simple scheduler for auto-cancellation of stale orders."""

    def __init__(self, db: Session):
        self.db = db

    async def run_auto_cancellation(
        self,
        tenant_id: Optional[int] = None,
        team_id: Optional[int] = None,
        system_user_id: int = 1
    ) -> dict:
        """
        Execute the auto-cancellation process for stale orders.

        This method should be called periodically (e.g., every 15-30 minutes)
        by an external scheduler or cron job.
        """
        try:
            logger.info(
                f"Starting auto-cancellation process for "
                f"tenant {tenant_id}, team {team_id}"
            )

            result = await cancel_stale_orders(
                db=self.db,
                tenant_id=tenant_id,
                team_id=team_id,
                system_user_id=system_user_id
            )

            if result["cancelled_count"] > 0:
                logger.info(
                    f"Auto-cancellation completed: "
                    f"{result['cancelled_count']} orders cancelled. "
                    f"Order IDs: {result['cancelled_orders']}"
                )
            else:
                logger.debug(
                    "Auto-cancellation completed: No stale orders found"
                )

            return result

        except Exception as e:
            logger.error(f"Auto-cancellation process failed: {str(e)}")
            return {
                "cancelled_count": 0,
                "cancelled_orders": [],
                "message": f"Auto-cancellation failed: {str(e)}"
            }
