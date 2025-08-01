# backend/modules/orders/tests/test_sync_service.py

"""
Tests for order synchronization service.

Tests sync service functionality including retry logic,
conflict detection, and batch processing.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
import httpx

from modules.orders.services.sync_service import OrderSyncService
from modules.orders.models.order_models import Order
from modules.orders.models.sync_models import (
    OrderSyncStatus, SyncStatus, SyncBatch,
    SyncConflict, SyncConfiguration
)
from modules.orders.tasks.sync_tasks import OrderSyncScheduler


class TestOrderSyncService:
    """Test order sync service"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock()
    
    @pytest.fixture
    def sync_service(self, mock_db):
        """Create sync service instance"""
        service = OrderSyncService(mock_db)
        # Mock HTTP client
        service.http_client = AsyncMock()
        return service
    
    @pytest.fixture
    def sample_order(self):
        """Create sample order"""
        order = Mock(spec=Order)
        order.id = 1
        order.external_id = None
        order.staff_id = 1
        order.customer_id = 1
        order.status = "completed"
        order.total_amount = 100.0
        order.is_synced = False
        order.sync_version = 1
        order.offline_created = True
        order.order_items = []
        return order
    
    @pytest.mark.asyncio
    async def test_sync_single_order_success(self, sync_service, mock_db, sample_order):
        """Test successful single order sync"""
        # Mock database queries
        mock_db.query().filter().first.return_value = sample_order
        
        sync_status = Mock(spec=OrderSyncStatus)
        sync_status.order_id = 1
        sync_status.sync_status = SyncStatus.PENDING
        sync_status.attempt_count = 0
        sync_status.error_count = 0
        
        mock_db.query().filter().first.side_effect = [sample_order, None]
        mock_db.add = Mock()
        mock_db.commit = Mock()
        
        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "id": "remote-123",
            "checksum": "abc123"
        }
        sync_service.http_client.post.return_value = mock_response
        
        # Run sync
        success, error = await sync_service.sync_single_order(1)
        
        assert success is True
        assert error is None
        assert sample_order.external_id == "remote-123"
        assert sample_order.is_synced is True
        assert sample_order.sync_version == 2
    
    @pytest.mark.asyncio
    async def test_sync_single_order_retry(self, sync_service, mock_db, sample_order):
        """Test order sync with retry logic"""
        mock_db.query().filter().first.return_value = sample_order
        
        sync_status = Mock(spec=OrderSyncStatus)
        sync_status.order_id = 1
        sync_status.sync_status = SyncStatus.RETRY
        sync_status.attempt_count = 1
        sync_status.error_count = 1
        
        mock_db.query().filter().first.side_effect = [sample_order, sync_status]
        
        # Mock failed HTTP response
        sync_service.http_client.post.side_effect = httpx.TimeoutException("Timeout")
        
        # Run sync
        success, error = await sync_service.sync_single_order(1)
        
        assert success is False
        assert "Timeout" in error
        assert sync_status.sync_status == SyncStatus.RETRY
        assert sync_status.attempt_count == 2
        assert sync_status.next_retry_at is not None
    
    @pytest.mark.asyncio
    async def test_sync_conflict_detection(self, sync_service, mock_db, sample_order):
        """Test conflict detection during sync"""
        mock_db.query().filter().first.return_value = sample_order
        
        sync_status = Mock(spec=OrderSyncStatus)
        mock_db.query().filter().first.side_effect = [sample_order, None]
        mock_db.add = Mock()
        mock_db.commit = Mock()
        
        # Mock conflict response
        mock_response = Mock()
        mock_response.status_code = 409
        mock_response.json.return_value = {
            "remote_data": {"total_amount": 120.0},
            "differences": {"total_amount": {"local": 100.0, "remote": 120.0}}
        }
        sync_service.http_client.post.return_value = mock_response
        
        # Run sync
        success, error = await sync_service.sync_single_order(1)
        
        assert success is False
        
        # Check conflict was created
        conflict_calls = [call for call in mock_db.add.call_args_list 
                         if isinstance(call[0][0], SyncConflict)]
        assert len(conflict_calls) > 0
    
    @pytest.mark.asyncio
    async def test_batch_sync(self, sync_service, mock_db):
        """Test batch sync processing"""
        # Create multiple orders
        orders = []
        for i in range(5):
            order = Mock(spec=Order)
            order.id = i + 1
            order.is_synced = False
            orders.append(order)
        
        mock_db.query().outerjoin().filter().limit().all.return_value = orders
        mock_db.query().join().filter().limit().all.return_value = []  # No retry orders
        
        # Mock batch creation
        batch = Mock(spec=SyncBatch)
        batch.id = 1
        batch.batch_id = "test-batch"
        batch.successful_syncs = 0
        batch.failed_syncs = 0
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        
        # Mock sync responses
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "remote-id", "checksum": "test"}
        sync_service.http_client.post.return_value = mock_response
        
        # Run batch sync
        with patch.object(sync_service, '_create_sync_batch', return_value=batch):
            with patch.object(sync_service, '_get_sync_config', return_value={"sync_enabled": True}):
                result = await sync_service.sync_pending_orders()
        
        assert result == batch
        assert batch.total_orders == 5


class TestOrderSyncScheduler:
    """Test sync scheduler"""
    
    @pytest.fixture
    def scheduler(self):
        """Create scheduler instance"""
        return OrderSyncScheduler()
    
    def test_scheduler_start_stop(self, scheduler):
        """Test scheduler start and stop"""
        # Start scheduler
        scheduler.start()
        assert scheduler.is_running is True
        assert scheduler.scheduler.running is True
        
        # Check jobs were added
        jobs = scheduler.scheduler.get_jobs()
        job_ids = [job.id for job in jobs]
        assert scheduler.sync_job_id in job_ids
        assert scheduler.health_check_job_id in job_ids
        assert scheduler.cleanup_job_id in job_ids
        
        # Stop scheduler
        scheduler.stop()
        assert scheduler.is_running is False
    
    def test_update_sync_interval(self, scheduler):
        """Test updating sync interval"""
        mock_db = Mock()
        mock_config = Mock()
        mock_db.query().filter().first.return_value = mock_config
        mock_db.commit = Mock()
        
        with patch('backend.modules.orders.tasks.sync_tasks.get_db', return_value=iter([mock_db])):
            result = scheduler.update_sync_interval(15)
        
        assert result is True
        assert mock_config.config_value == 15
    
    def test_trigger_manual_sync(self, scheduler):
        """Test manual sync trigger"""
        scheduler.start()
        
        result = scheduler.trigger_manual_sync()
        assert result is True
        
        # Check manual sync job was added
        jobs = scheduler.scheduler.get_jobs()
        manual_jobs = [j for j in jobs if "manual_sync" in j.id]
        assert len(manual_jobs) > 0
        
        scheduler.stop()


class TestSyncConfiguration:
    """Test sync configuration"""
    
    def test_get_config(self):
        """Test configuration retrieval"""
        mock_db = Mock()
        mock_config = Mock()
        mock_config.config_value = {"test": "value"}
        
        mock_db.query().filter().first.return_value = mock_config
        
        result = SyncConfiguration.get_config(mock_db, "test_key")
        assert result == {"test": "value"}
        
        # Test default value
        mock_db.query().filter().first.return_value = None
        result = SyncConfiguration.get_config(mock_db, "missing_key", "default")
        assert result == "default"


@pytest.mark.asyncio
async def test_sync_service_cleanup():
    """Test sync service cleanup"""
    mock_db = Mock()
    service = OrderSyncService(mock_db)
    
    # Mock http client
    service.http_client = AsyncMock()
    service.http_client.aclose = AsyncMock()
    
    await service.close()
    
    service.http_client.aclose.assert_called_once()