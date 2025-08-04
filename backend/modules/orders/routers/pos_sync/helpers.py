# backend/modules/orders/routers/pos_sync/helpers.py

"""
Helper functions for POS sync operations.
"""

from typing import List
from contextlib import closing
import logging

from core.database import get_db
from modules.orders.services.sync_service import OrderSyncService
from core.config import settings

logger = logging.getLogger(__name__)


async def process_sync_batch(order_ids: List[int], terminal_id: str, batch_size: int = None):
    """
    Process sync batch in background with proper resource management.
    
    Args:
        order_ids: List of order IDs to sync
        terminal_id: Terminal identifier
        batch_size: Optional batch size for processing (defaults to config)
    """
    batch_size = batch_size or settings.SYNC_BATCH_SIZE
    
    # Use closing context manager to ensure DB connection is properly closed
    with closing(next(get_db())) as db:
        try:
            sync_service = OrderSyncService(db)
            
            # Process orders in batches to avoid overwhelming the system
            for i in range(0, len(order_ids), batch_size):
                batch = order_ids[i:i + batch_size]
                
                for order_id in batch:
                    try:
                        await sync_service.sync_single_order(order_id)
                    except Exception as e:
                        logger.error(
                            f"Error syncing order {order_id}: {str(e)}",
                            extra={
                                "terminal_id": terminal_id,
                                "order_id": order_id,
                                "batch_index": i // batch_size
                            },
                            exc_info=True
                        )
                
                # Log batch progress
                logger.info(
                    f"Processed sync batch {i // batch_size + 1}/{(len(order_ids) + batch_size - 1) // batch_size}",
                    extra={
                        "terminal_id": terminal_id,
                        "processed": min(i + batch_size, len(order_ids)),
                        "total": len(order_ids)
                    }
                )
            
            await sync_service.close()
            
        except Exception as e:
            logger.error(
                f"Error in sync batch processing: {str(e)}",
                extra={"terminal_id": terminal_id},
                exc_info=True
            )
            raise