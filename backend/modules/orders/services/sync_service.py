# backend/modules/orders/services/sync_service.py

"""
Order synchronization service for handling offline/online sync.

Manages order synchronization between local POS and cloud systems,
including retry logic, conflict resolution, and batch processing.
"""

import logging
import asyncio
import hashlib
import json
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
import httpx

from core.database import get_db
from modules.orders.models.order_models import Order, OrderItem
from modules.orders.models.sync_models import (
    OrderSyncStatus,
    SyncStatus,
    SyncDirection,
    SyncBatch,
    SyncLog,
    SyncConfiguration,
    SyncConflict,
)
from modules.orders.schemas.order_schemas import OrderCreate, OrderUpdate
from core.config import settings

logger = logging.getLogger(__name__)


class OrderSyncService:
    """Service for synchronizing orders between local and remote systems"""

    def __init__(self, db: Session):
        self.db = db
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.max_retry_attempts = 3
        self.retry_backoff_base = 2  # Exponential backoff base
        self.batch_size = 50
        self.sync_endpoint = settings.CLOUD_SYNC_ENDPOINT
        self.api_key = settings.CLOUD_API_KEY

    async def sync_pending_orders(self) -> SyncBatch:
        """
        Main method to sync all pending orders.
        Called by the background scheduler every 10 minutes.
        """
        batch = self._create_sync_batch("scheduled")

        try:
            # Get configuration
            config = self._get_sync_config()
            if not config.get("sync_enabled", True):
                logger.info("Order sync is disabled in configuration")
                return self._complete_batch(batch, "disabled")

            # Get pending orders
            pending_orders = self._get_pending_orders()
            batch.total_orders = len(pending_orders)

            if not pending_orders:
                logger.info("No pending orders to sync")
                return self._complete_batch(batch, "no_orders")

            logger.info(
                f"Starting sync batch {batch.batch_id} with {len(pending_orders)} orders"
            )

            # Process orders in batches
            for i in range(0, len(pending_orders), self.batch_size):
                batch_orders = pending_orders[i : i + self.batch_size]
                await self._sync_order_batch(batch_orders, batch)

            # Handle retry orders
            retry_orders = self._get_retry_orders()
            if retry_orders:
                logger.info(f"Processing {len(retry_orders)} retry orders")
                await self._sync_order_batch(retry_orders, batch)

            # Complete batch
            return self._complete_batch(batch, "completed")

        except (httpx.HTTPError, asyncio.TimeoutError, ValueError) as e:
            logger.error(f"Sync batch {batch.batch_id} failed: {e}", exc_info=True)
            return self._complete_batch(batch, "failed", str(e))
        except Exception as e:
            logger.critical(
                f"Unexpected error in sync batch {batch.batch_id}: {e}", exc_info=True
            )
            return self._complete_batch(batch, "failed", f"Critical error: {str(e)}")

    async def sync_single_order(self, order_id: int) -> Tuple[bool, Optional[str]]:
        """
        Sync a single order immediately.
        Used for manual sync or high-priority orders.
        """
        order = self.db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return False, "Order not found"

        sync_status = self._get_or_create_sync_status(order)

        try:
            result = await self._sync_order(order, sync_status)
            return result, None
        except (httpx.HTTPError, asyncio.TimeoutError) as e:
            error_msg = f"Network error syncing order {order_id}: {e}"
            logger.error(error_msg)
            return False, error_msg
        except ValueError as e:
            error_msg = f"Data validation error for order {order_id}: {e}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error syncing order {order_id}: {e}"
            logger.critical(error_msg, exc_info=True)
            return False, error_msg

    async def _sync_order_batch(self, orders: List[Order], batch: SyncBatch) -> None:
        """Sync a batch of orders concurrently"""
        tasks = []

        for order in orders:
            sync_status = self._get_or_create_sync_status(order)
            tasks.append(self._sync_order_with_logging(order, sync_status, batch))

        # Run sync tasks concurrently with limited concurrency
        semaphore = asyncio.Semaphore(10)  # Max 10 concurrent syncs

        async def bounded_sync(task):
            async with semaphore:
                return await task

        results = await asyncio.gather(
            *[bounded_sync(task) for task in tasks], return_exceptions=True
        )

        # Update batch statistics
        for result in results:
            if isinstance(result, Exception):
                batch.failed_syncs += 1
            elif result:
                batch.successful_syncs += 1
            else:
                batch.failed_syncs += 1

    async def _sync_order_with_logging(
        self, order: Order, sync_status: OrderSyncStatus, batch: SyncBatch
    ) -> bool:
        """Sync order with detailed logging"""
        sync_log = SyncLog(
            batch_id=batch.id,
            order_id=order.id,
            operation="update" if order.external_id else "create",
            sync_direction=SyncDirection.LOCAL_TO_REMOTE,
            started_at=datetime.utcnow(),
            data_before=self._serialize_order(order),
        )

        try:
            result = await self._sync_order(order, sync_status)

            sync_log.status = "success" if result else "failed"
            sync_log.completed_at = datetime.utcnow()
            sync_log.duration_ms = int(
                (sync_log.completed_at - sync_log.started_at).total_seconds() * 1000
            )

            if result:
                sync_log.data_after = self._serialize_order(order)
                sync_log.changes_made = self._calculate_changes(
                    sync_log.data_before, sync_log.data_after
                )

            self.db.add(sync_log)
            self.db.commit()

            return result

        except httpx.HTTPStatusError as e:
            sync_log.status = "failed"
            sync_log.error_message = f"HTTP {e.response.status_code}: {str(e)}"
            sync_log.http_status_code = e.response.status_code
        except httpx.TimeoutException:
            sync_log.status = "failed"
            sync_log.error_message = "Request timeout"
            sync_log.error_code = "TIMEOUT"
        except httpx.HTTPError as e:
            sync_log.status = "failed"
            sync_log.error_message = f"HTTP error: {str(e)}"
            sync_log.error_code = "HTTP_ERROR"
        except Exception as e:
            sync_log.status = "failed"
            sync_log.error_message = f"Unexpected error: {str(e)}"
            sync_log.error_code = "UNKNOWN"
            sync_log.completed_at = datetime.utcnow()
            sync_log.duration_ms = int(
                (sync_log.completed_at - sync_log.started_at).total_seconds() * 1000
            )

            self.db.add(sync_log)
            self.db.commit()

            raise

    async def _sync_order(self, order: Order, sync_status: OrderSyncStatus) -> bool:
        """
        Sync a single order to remote system.
        Returns True if successful, False otherwise.
        """
        # Update sync status
        sync_status.sync_status = SyncStatus.IN_PROGRESS
        sync_status.last_attempt_at = datetime.utcnow()
        sync_status.attempt_count += 1
        self.db.commit()

        try:
            # Calculate checksum
            order_data = self._serialize_order(order)
            local_checksum = self._calculate_checksum(order_data)
            sync_status.local_checksum = local_checksum

            # Prepare request
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "X-POS-Terminal-ID": settings.POS_TERMINAL_ID,
                "X-Sync-Version": str(order.sync_version),
            }

            # Send to remote system
            if order.external_id:
                # Update existing order
                response = await self.http_client.put(
                    f"{self.sync_endpoint}/orders/{order.external_id}",
                    json=order_data,
                    headers=headers,
                )
            else:
                # Create new order
                response = await self.http_client.post(
                    f"{self.sync_endpoint}/orders", json=order_data, headers=headers
                )

            # Handle response
            if response.status_code in (200, 201):
                remote_data = response.json()

                # Update order with remote data
                order.external_id = remote_data.get("id")
                order.is_synced = True
                order.last_sync_at = datetime.utcnow()
                order.sync_version += 1

                # Update sync status
                sync_status.sync_status = SyncStatus.SYNCED
                sync_status.synced_at = datetime.utcnow()
                sync_status.remote_id = order.external_id
                sync_status.remote_checksum = remote_data.get("checksum")
                sync_status.error_count = 0
                sync_status.last_error = None
                sync_status.next_retry_at = None

                self.db.commit()
                logger.info(f"Successfully synced order {order.id}")
                return True

            elif response.status_code == 409:
                # Conflict detected
                await self._handle_conflict(order, sync_status, response.json())
                return False

            else:
                # Sync failed
                error_msg = f"HTTP {response.status_code}: {response.text}"
                self._handle_sync_error(sync_status, error_msg, response.status_code)
                return False

        except httpx.TimeoutException:
            self._handle_sync_error(sync_status, "Request timeout", "TIMEOUT")
            return False

        except httpx.RequestError as e:
            self._handle_sync_error(sync_status, f"Network error: {e}", "NETWORK")
            return False

        except httpx.HTTPStatusError as e:
            self._handle_sync_error(
                sync_status,
                f"HTTP {e.response.status_code}: {str(e)}",
                f"HTTP_{e.response.status_code}",
            )
            logger.error(f"HTTP error syncing order {order.id}: {e}")
            return False
        except httpx.TimeoutException:
            self._handle_sync_error(sync_status, "Request timeout", "TIMEOUT")
            logger.warning(f"Timeout syncing order {order.id}")
            return False
        except httpx.HTTPError as e:
            self._handle_sync_error(sync_status, f"Network error: {e}", "NETWORK_ERROR")
            logger.error(f"Network error syncing order {order.id}: {e}")
            return False
        except ValueError as e:
            self._handle_sync_error(
                sync_status, f"Data validation error: {e}", "VALIDATION_ERROR"
            )
            logger.error(f"Validation error for order {order.id}: {e}")
            return False
        except Exception as e:
            self._handle_sync_error(sync_status, f"Unexpected error: {e}", "UNKNOWN")
            logger.critical(
                f"Unexpected sync error for order {order.id}: {e}", exc_info=True
            )
            return False

    async def _handle_conflict(
        self, order: Order, sync_status: OrderSyncStatus, conflict_data: Dict[str, Any]
    ) -> None:
        """Handle sync conflicts"""
        logger.warning(f"Conflict detected for order {order.id}")

        # Create conflict record
        conflict = SyncConflict(
            order_id=order.id,
            conflict_type="version_conflict",
            local_data=self._serialize_order(order),
            remote_data=conflict_data.get("remote_data", {}),
            differences=conflict_data.get("differences", {}),
        )

        # Update sync status
        sync_status.sync_status = SyncStatus.CONFLICT
        sync_status.conflict_detected_at = datetime.utcnow()
        sync_status.conflict_data = conflict_data

        # Auto-resolve if configured
        config = self._get_sync_config()
        if config.get("conflict_resolution_mode") == "auto":
            resolution = config.get("conflict_resolution_strategy", "local_wins")

            if resolution == "local_wins":
                # Force update with local version
                conflict.resolution_method = "local_wins"
                conflict.resolution_status = "resolved"
                conflict.resolved_at = datetime.utcnow()
                conflict.final_data = self._serialize_order(order)

                # Retry sync with force flag
                sync_status.sync_status = SyncStatus.RETRY
                sync_status.next_retry_at = datetime.utcnow() + timedelta(minutes=1)

            elif resolution == "remote_wins":
                # Update local with remote version
                self._update_order_from_remote(order, conflict_data["remote_data"])
                conflict.resolution_method = "remote_wins"
                conflict.resolution_status = "resolved"
                conflict.resolved_at = datetime.utcnow()
                conflict.final_data = conflict_data["remote_data"]

                sync_status.sync_status = SyncStatus.SYNCED
                sync_status.synced_at = datetime.utcnow()

        self.db.add(conflict)
        self.db.commit()

    def _handle_sync_error(
        self,
        sync_status: OrderSyncStatus,
        error_message: str,
        error_code: Optional[str] = None,
    ) -> None:
        """Handle sync errors with retry logic"""
        sync_status.last_error = error_message
        sync_status.error_code = error_code
        sync_status.error_count += 1

        if sync_status.attempt_count >= self.max_retry_attempts:
            # Max retries reached
            sync_status.sync_status = SyncStatus.FAILED
            logger.error(
                f"Order {sync_status.order_id} sync failed after "
                f"{self.max_retry_attempts} attempts: {error_message}"
            )
        else:
            # Schedule retry with exponential backoff
            retry_delay = self.retry_backoff_base**sync_status.attempt_count
            sync_status.sync_status = SyncStatus.RETRY
            sync_status.next_retry_at = datetime.utcnow() + timedelta(
                minutes=retry_delay
            )
            logger.warning(
                f"Order {sync_status.order_id} sync failed, "
                f"retry scheduled in {retry_delay} minutes"
            )

        self.db.commit()

    def _get_pending_orders(self) -> List[Order]:
        """Get orders that need to be synced"""
        # Get orders without sync status or with pending status
        orders = (
            self.db.query(Order)
            .outerjoin(OrderSyncStatus)
            .filter(
                or_(
                    Order.is_synced == False,
                    OrderSyncStatus.sync_status == SyncStatus.PENDING,
                    OrderSyncStatus.id == None,
                )
            )
            .limit(self.batch_size * 2)
            .all()
        )

        return orders

    def _get_retry_orders(self) -> List[Order]:
        """Get orders scheduled for retry"""
        now = datetime.utcnow()

        orders = (
            self.db.query(Order)
            .join(OrderSyncStatus)
            .filter(
                OrderSyncStatus.sync_status == SyncStatus.RETRY,
                OrderSyncStatus.next_retry_at <= now,
            )
            .limit(self.batch_size)
            .all()
        )

        return orders

    def _get_or_create_sync_status(self, order: Order) -> OrderSyncStatus:
        """Get or create sync status for an order"""
        sync_status = (
            self.db.query(OrderSyncStatus)
            .filter(OrderSyncStatus.order_id == order.id)
            .first()
        )

        if not sync_status:
            sync_status = OrderSyncStatus(
                order_id=order.id,
                sync_status=SyncStatus.PENDING,
                sync_direction=SyncDirection.LOCAL_TO_REMOTE,
            )
            self.db.add(sync_status)
            self.db.commit()

        return sync_status

    def _serialize_order(self, order: Order) -> Dict[str, Any]:
        """Serialize order to JSON-compatible format"""
        order_data = {
            "id": order.id,
            "external_id": order.external_id,
            "staff_id": order.staff_id,
            "customer_id": order.customer_id,
            "table_no": order.table_no,
            "status": order.status,
            "category_id": order.category_id,
            "customer_notes": order.customer_notes,
            "priority": order.priority.value if order.priority else "normal",
            "subtotal": float(order.subtotal) if order.subtotal else 0,
            "discount_amount": (
                float(order.discount_amount) if order.discount_amount else 0
            ),
            "tax_amount": float(order.tax_amount) if order.tax_amount else 0,
            "total_amount": float(order.total_amount) if order.total_amount else 0,
            "final_amount": float(order.final_amount) if order.final_amount else 0,
            "offline_created": order.offline_created,
            "sync_version": order.sync_version,
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "updated_at": order.updated_at.isoformat() if order.updated_at else None,
            "items": [],
        }

        # Add order items
        for item in order.order_items:
            order_data["items"].append(
                {
                    "menu_item_id": item.menu_item_id,
                    "quantity": item.quantity,
                    "price": float(item.price),
                    "amount": (
                        float(item.amount)
                        if hasattr(item, "amount")
                        else float(item.price * item.quantity)
                    ),
                    "instructions": (
                        item.instructions if hasattr(item, "instructions") else None
                    ),
                }
            )

        return order_data

    def _calculate_checksum(self, data: Dict[str, Any]) -> str:
        """Calculate checksum for data integrity"""
        # Sort keys for consistent checksum
        sorted_data = json.dumps(data, sort_keys=True)
        return hashlib.sha256(sorted_data.encode()).hexdigest()

    def _calculate_changes(
        self, before: Dict[str, Any], after: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate changes between two versions"""
        changes = {}

        for key in set(before.keys()) | set(after.keys()):
            if key not in before:
                changes[key] = {"added": after[key]}
            elif key not in after:
                changes[key] = {"removed": before[key]}
            elif before[key] != after[key]:
                changes[key] = {"before": before[key], "after": after[key]}

        return changes

    def _update_order_from_remote(
        self, order: Order, remote_data: Dict[str, Any]
    ) -> None:
        """Update local order with remote data"""
        # Update order fields
        order.external_id = remote_data.get("id")
        order.status = remote_data.get("status", order.status)
        order.total_amount = remote_data.get("total_amount", order.total_amount)
        order.final_amount = remote_data.get("final_amount", order.final_amount)
        order.is_synced = True
        order.last_sync_at = datetime.utcnow()
        order.sync_version = remote_data.get("sync_version", order.sync_version + 1)

        self.db.commit()

    def _create_sync_batch(self, batch_type: str) -> SyncBatch:
        """Create a new sync batch"""
        batch = SyncBatch(
            batch_type=batch_type,
            initiated_by="system",
            pos_terminal_id=settings.POS_TERMINAL_ID,
        )
        self.db.add(batch)
        self.db.commit()
        return batch

    def _complete_batch(
        self, batch: SyncBatch, status: str, error: Optional[str] = None
    ) -> SyncBatch:
        """Complete a sync batch"""
        batch.completed_at = datetime.utcnow()
        batch.duration_ms = int(
            (batch.completed_at - batch.started_at).total_seconds() * 1000
        )

        if error:
            batch.error_summary = {"error": error, "status": status}

        # Calculate performance metrics
        if batch.successful_syncs > 0:
            sync_times = (
                self.db.query(
                    func.avg(SyncLog.duration_ms),
                    func.max(SyncLog.duration_ms),
                    func.min(SyncLog.duration_ms),
                )
                .filter(SyncLog.batch_id == batch.id, SyncLog.status == "success")
                .first()
            )

            if sync_times:
                batch.avg_sync_time_ms = sync_times[0]
                batch.max_sync_time_ms = sync_times[1]
                batch.min_sync_time_ms = sync_times[2]

        self.db.commit()

        logger.info(
            f"Sync batch {batch.batch_id} completed: "
            f"{batch.successful_syncs} success, {batch.failed_syncs} failed, "
            f"{batch.conflict_count} conflicts"
        )

        return batch

    def _get_sync_config(self) -> Dict[str, Any]:
        """Get sync configuration"""
        config = {}

        # Load configuration from database
        config_keys = [
            "sync_enabled",
            "sync_interval_minutes",
            "max_retry_attempts",
            "retry_backoff_multiplier",
            "batch_size",
            "conflict_resolution_mode",
            "conflict_resolution_strategy",
        ]

        for key in config_keys:
            value = SyncConfiguration.get_config(self.db, key)
            if value is not None:
                config[key] = value

        # Apply defaults
        config.setdefault("sync_enabled", True)
        config.setdefault("sync_interval_minutes", 10)
        config.setdefault("max_retry_attempts", self.max_retry_attempts)
        config.setdefault("retry_backoff_multiplier", self.retry_backoff_base)
        config.setdefault("batch_size", self.batch_size)
        config.setdefault("conflict_resolution_mode", "manual")
        config.setdefault("conflict_resolution_strategy", "local_wins")

        return config

    async def get_sync_status(self) -> Dict[str, Any]:
        """Get current sync status summary"""
        # Count orders by sync status
        status_counts = (
            self.db.query(OrderSyncStatus.sync_status, func.count(OrderSyncStatus.id))
            .group_by(OrderSyncStatus.sync_status)
            .all()
        )

        # Get unsynced orders count
        unsynced_count = self.db.query(Order).filter(Order.is_synced == False).count()

        # Get last batch info
        last_batch = (
            self.db.query(SyncBatch).order_by(SyncBatch.started_at.desc()).first()
        )

        # Get conflict count
        pending_conflicts = (
            self.db.query(SyncConflict)
            .filter(SyncConflict.resolution_status == "pending")
            .count()
        )

        return {
            "sync_status_counts": dict(status_counts),
            "unsynced_orders": unsynced_count,
            "pending_conflicts": pending_conflicts,
            "last_batch": (
                {
                    "batch_id": str(last_batch.batch_id) if last_batch else None,
                    "started_at": (
                        last_batch.started_at.isoformat() if last_batch else None
                    ),
                    "completed_at": (
                        last_batch.completed_at.isoformat()
                        if last_batch and last_batch.completed_at
                        else None
                    ),
                    "successful_syncs": (
                        last_batch.successful_syncs if last_batch else 0
                    ),
                    "failed_syncs": last_batch.failed_syncs if last_batch else 0,
                }
                if last_batch
                else None
            ),
        }

    async def close(self):
        """Clean up resources"""
        await self.http_client.aclose()
