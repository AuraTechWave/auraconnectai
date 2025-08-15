# backend/modules/orders/tests/test_sync_integration.py

"""
Integration tests for order synchronization.

Tests conflict resolution endpoints and scheduler lifecycle.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch, AsyncMock

from app.main import app
from core.database import get_db
from modules.orders.models.order_models import Order
from modules.orders.models.sync_models import (
    OrderSyncStatus,
    SyncStatus,
    SyncConflict,
    SyncConfiguration,
)
from modules.orders.tasks.sync_tasks import OrderSyncScheduler
from modules.staff.models.staff_models import StaffMember


class TestConflictResolutionIntegration:
    """Integration tests for conflict resolution API"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self, client):
        """Get authentication headers"""
        # Mock authentication for tests
        return {"Authorization": "Bearer test-token"}

    @pytest.fixture
    def db_session(self):
        """Create test database session"""
        db = next(get_db())
        yield db
        db.rollback()
        db.close()

    @pytest.fixture
    def sample_conflict(self, db_session):
        """Create a sample conflict"""
        # Create order
        order = Order(
            id=1, staff_id=1, customer_id=1, status="completed", total_amount=100.0
        )
        db_session.add(order)

        # Create sync status
        sync_status = OrderSyncStatus(order_id=1, sync_status=SyncStatus.CONFLICT)
        db_session.add(sync_status)

        # Create conflict
        conflict = SyncConflict(
            order_id=1,
            conflict_type="data_mismatch",
            local_data={"total_amount": 100.0},
            remote_data={"total_amount": 120.0},
            differences={"total_amount": {"local": 100.0, "remote": 120.0}},
            resolution_status="pending",
        )
        db_session.add(conflict)
        db_session.commit()

        return conflict

    def test_get_conflicts(self, client, auth_headers, sample_conflict):
        """Test retrieving conflicts"""
        with patch(
            "backend.core.auth.get_current_user", return_value=Mock(id=1, role="admin")
        ):
            response = client.get("/api/orders/sync/conflicts", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["order_id"] == sample_conflict.order_id
        assert data[0]["resolution_status"] == "pending"

    def test_resolve_conflict_local_wins(
        self, client, auth_headers, sample_conflict, db_session
    ):
        """Test resolving conflict with local data winning"""
        with patch(
            "backend.core.auth.get_current_user", return_value=Mock(id=1, role="admin")
        ):
            response = client.post(
                f"/api/orders/sync/conflicts/{sample_conflict.id}/resolve",
                headers=auth_headers,
                json={
                    "resolution_method": "local_wins",
                    "notes": "Local data is correct",
                },
            )

        assert response.status_code == 200
        assert response.json()["status"] == "resolved"

        # Verify conflict was updated
        db_session.refresh(sample_conflict)
        assert sample_conflict.resolution_status == "resolved"
        assert sample_conflict.resolution_method == "local_wins"
        assert sample_conflict.resolved_by == 1

        # Verify sync status was updated for retry
        sync_status = (
            db_session.query(OrderSyncStatus)
            .filter(OrderSyncStatus.order_id == sample_conflict.order_id)
            .first()
        )
        assert sync_status.sync_status == SyncStatus.RETRY

    def test_resolve_conflict_remote_wins(
        self, client, auth_headers, sample_conflict, db_session
    ):
        """Test resolving conflict with remote data winning"""
        with patch(
            "backend.core.auth.get_current_user", return_value=Mock(id=1, role="admin")
        ):
            response = client.post(
                f"/api/orders/sync/conflicts/{sample_conflict.id}/resolve",
                headers=auth_headers,
                json={
                    "resolution_method": "remote_wins",
                    "notes": "Remote data is correct",
                },
            )

        assert response.status_code == 200

        # Verify sync status was marked as synced
        sync_status = (
            db_session.query(OrderSyncStatus)
            .filter(OrderSyncStatus.order_id == sample_conflict.order_id)
            .first()
        )
        assert sync_status.sync_status == SyncStatus.SYNCED

    def test_resolve_conflict_merge(self, client, auth_headers, sample_conflict):
        """Test resolving conflict with merge"""
        with patch(
            "backend.core.auth.get_current_user", return_value=Mock(id=1, role="admin")
        ):
            response = client.post(
                f"/api/orders/sync/conflicts/{sample_conflict.id}/resolve",
                headers=auth_headers,
                json={
                    "resolution_method": "merge",
                    "notes": "Merged data",
                    "final_data": {"total_amount": 110.0},
                },
            )

        assert response.status_code == 200

    def test_resolve_nonexistent_conflict(self, client, auth_headers):
        """Test resolving non-existent conflict"""
        with patch(
            "backend.core.auth.get_current_user", return_value=Mock(id=1, role="admin")
        ):
            response = client.post(
                "/api/orders/sync/conflicts/999/resolve",
                headers=auth_headers,
                json={"resolution_method": "local_wins", "notes": "Test"},
            )

        assert response.status_code == 404
        assert "Conflict not found" in response.json()["detail"]

    def test_resolve_already_resolved_conflict(
        self, client, auth_headers, sample_conflict, db_session
    ):
        """Test resolving already resolved conflict"""
        # Mark conflict as resolved
        sample_conflict.resolution_status = "resolved"
        db_session.commit()

        with patch(
            "backend.core.auth.get_current_user", return_value=Mock(id=1, role="admin")
        ):
            response = client.post(
                f"/api/orders/sync/conflicts/{sample_conflict.id}/resolve",
                headers=auth_headers,
                json={"resolution_method": "local_wins", "notes": "Test"},
            )

        assert response.status_code == 400
        assert "Conflict already resolved" in response.json()["detail"]


class TestSchedulerLifecycleIntegration:
    """Integration tests for scheduler lifecycle"""

    @pytest.fixture
    def scheduler(self):
        """Create test scheduler instance"""
        return OrderSyncScheduler()

    @pytest.fixture
    def mock_sync_service(self):
        """Mock sync service"""
        with patch("backend.modules.orders.tasks.sync_tasks.OrderSyncService") as mock:
            instance = AsyncMock()
            instance.sync_pending_orders.return_value = Mock(
                batch_id="test-batch", successful_syncs=5, failed_syncs=0
            )
            mock.return_value = instance
            yield instance

    @pytest.mark.asyncio
    async def test_scheduler_startup_shutdown(self, scheduler):
        """Test scheduler startup and shutdown"""
        # Test startup
        scheduler.start()
        assert scheduler.is_running is True
        assert scheduler.scheduler.running is True

        # Verify jobs were scheduled
        jobs = scheduler.scheduler.get_jobs()
        job_ids = [job.id for job in jobs]
        assert scheduler.sync_job_id in job_ids
        assert scheduler.health_check_job_id in job_ids
        assert scheduler.cleanup_job_id in job_ids

        # Test shutdown
        scheduler.stop()
        assert scheduler.is_running is False
        assert not scheduler.scheduler.running

    @pytest.mark.asyncio
    async def test_manual_sync_trigger(self, scheduler, mock_sync_service):
        """Test manual sync trigger"""
        scheduler.start()

        # Trigger manual sync
        result = scheduler.trigger_manual_sync()
        assert result is True

        # Wait briefly for job to be scheduled
        await asyncio.sleep(0.1)

        # Check that manual sync job was added
        jobs = scheduler.scheduler.get_jobs()
        manual_jobs = [j for j in jobs if "manual_sync" in j.id]
        assert len(manual_jobs) > 0

        scheduler.stop()

    def test_update_sync_interval(self, scheduler):
        """Test updating sync interval"""
        scheduler.start()

        with patch("backend.modules.orders.tasks.sync_tasks.get_db") as mock_get_db:
            mock_db = Mock()
            mock_config = Mock()
            mock_db.query().filter().first.return_value = mock_config
            mock_get_db.return_value = iter([mock_db])

            # Update interval
            result = scheduler.update_sync_interval(15)
            assert result is True
            assert mock_config.config_value == 15

            # Verify job was rescheduled
            jobs = scheduler.scheduler.get_jobs()
            sync_job = next(j for j in jobs if j.id == scheduler.sync_job_id)
            assert "every 15 minutes" in sync_job.name

        scheduler.stop()

    @pytest.mark.asyncio
    async def test_sync_task_execution(self, scheduler, mock_sync_service):
        """Test sync task execution"""
        scheduler.start()

        with patch("backend.modules.orders.tasks.sync_tasks.get_db") as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value = iter([mock_db])

            # Execute sync task
            await scheduler._sync_task()

            # Verify sync service was called
            mock_sync_service.sync_pending_orders.assert_called_once()

        scheduler.stop()

    @pytest.mark.asyncio
    async def test_health_check_execution(self, scheduler):
        """Test health check execution"""
        scheduler.start()

        with patch("backend.modules.orders.tasks.sync_tasks.get_db") as mock_get_db:
            mock_db = Mock()

            # Mock database queries
            mock_db.query().filter().count.return_value = 0
            mock_db.query().filter().all.return_value = []
            mock_get_db.return_value = iter([mock_db])

            # Execute health check
            await scheduler._health_check_task()

            # Verify queries were made
            assert mock_db.query.called

        scheduler.stop()

    def test_concurrent_scheduler_instances(self):
        """Test that multiple scheduler instances are prevented"""
        scheduler1 = OrderSyncScheduler()
        scheduler2 = OrderSyncScheduler()

        scheduler1.start()

        # Second scheduler should fail to start
        with pytest.raises(RuntimeError):
            scheduler2.start()

        scheduler1.stop()

    @pytest.mark.asyncio
    async def test_scheduler_error_handling(self, scheduler):
        """Test scheduler error handling"""
        scheduler.start()

        with patch(
            "backend.modules.orders.tasks.sync_tasks.OrderSyncService"
        ) as mock_service:
            # Mock sync service to raise error
            mock_service.side_effect = Exception("Test error")

            with patch("backend.modules.orders.tasks.sync_tasks.get_db") as mock_get_db:
                mock_db = Mock()
                mock_get_db.return_value = iter([mock_db])

                # Execute sync task - should handle error gracefully
                await scheduler._sync_task()

                # Scheduler should still be running
                assert scheduler.is_running

        scheduler.stop()


class TestManualSyncIntegration:
    """Integration tests for manual sync endpoint"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_manual_sync_all_orders(self, client):
        """Test manual sync for all pending orders"""
        with patch(
            "backend.core.auth.get_current_user", return_value=Mock(id=1, role="admin")
        ):
            with patch(
                "backend.modules.orders.tasks.sync_tasks.order_sync_scheduler.trigger_manual_sync",
                return_value=True,
            ):
                response = client.post(
                    "/api/orders/sync/manual",
                    headers={"Authorization": "Bearer test-token"},
                    json={},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "full_sync"
        assert data["status"] == "scheduled"

    @pytest.mark.asyncio
    async def test_manual_sync_specific_orders(self, client):
        """Test manual sync for specific orders"""
        with patch(
            "backend.core.auth.get_current_user", return_value=Mock(id=1, role="admin")
        ):
            with patch(
                "backend.modules.orders.services.sync_service.OrderSyncService"
            ) as mock_service:
                instance = Mock()
                instance.sync_single_order = AsyncMock(return_value=(True, None))
                instance.close = AsyncMock()
                mock_service.return_value = instance

                response = client.post(
                    "/api/orders/sync/manual",
                    headers={"Authorization": "Bearer test-token"},
                    json={"order_ids": [1, 2, 3]},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "specific_orders"
        assert data["total"] == 3
        assert data["successful"] == 3
