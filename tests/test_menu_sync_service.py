# tests/test_menu_sync_service.py

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.core.menu_sync_service import MenuSyncService
from backend.core.menu_sync_models import (
    MenuSyncJob, MenuSyncConfig, POSMenuMapping, MenuSyncLog, MenuSyncConflict,
    SyncDirection, SyncStatus, ConflictResolution
)
from backend.core.menu_sync_schemas import StartSyncRequest
from backend.modules.pos.models.pos_integration import POSIntegration


class TestMenuSyncService:
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def sync_service(self, mock_db):
        """Create MenuSyncService with mocked dependencies"""
        with patch('backend.core.menu_sync_service.MenuVersioningService'):
            return MenuSyncService(mock_db)
    
    @pytest.fixture
    def sample_pos_integration(self):
        """Sample POS integration for testing"""
        integration = Mock(spec=POSIntegration)
        integration.id = 1
        integration.vendor = "square"
        integration.credentials = {"access_token": "test_token"}
        return integration
    
    @pytest.fixture
    def sample_sync_config(self):
        """Sample sync configuration for testing"""
        config = Mock(spec=MenuSyncConfig)
        config.pos_integration_id = 1
        config.sync_enabled = True
        config.max_concurrent_jobs = 3
        config.default_conflict_resolution = ConflictResolution.MANUAL
        config.create_version_on_pull = True
        return config
    
    @pytest.fixture
    def sample_sync_request(self):
        """Sample sync request for testing"""
        return StartSyncRequest(
            pos_integration_id=1,
            sync_direction=SyncDirection.BIDIRECTIONAL,
            entity_types=["category", "item"],
            force_sync=False
        )

    def test_get_pos_adapter_square(self, sync_service, sample_pos_integration):
        """Test getting Square POS adapter"""
        sample_pos_integration.vendor = "square"
        
        with patch('backend.core.menu_sync_service.SquareAdapter') as MockAdapter:
            adapter = sync_service.get_pos_adapter(sample_pos_integration)
            MockAdapter.assert_called_once_with(sample_pos_integration.credentials)
    
    def test_get_pos_adapter_unsupported_vendor(self, sync_service, sample_pos_integration):
        """Test error handling for unsupported POS vendor"""
        sample_pos_integration.vendor = "unsupported_vendor"
        
        with pytest.raises(ValueError, match="Unsupported POS vendor"):
            sync_service.get_pos_adapter(sample_pos_integration)

    @pytest.mark.asyncio
    async def test_start_sync_success(self, sync_service, mock_db, sample_pos_integration, 
                                    sample_sync_config, sample_sync_request):
        """Test successful sync job creation"""
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            sample_pos_integration,  # POS integration query
            sample_sync_config       # Sync config query
        ]
        mock_db.query.return_value.filter.return_value.count.return_value = 0  # No active jobs
        
        # Mock the async execution
        with patch.object(sync_service, '_execute_sync_job', new_callable=AsyncMock):
            job = await sync_service.start_sync(sample_sync_request, user_id=123)
            
            assert isinstance(job, MenuSyncJob)
            assert job.pos_integration_id == 1
            assert job.sync_direction == SyncDirection.BIDIRECTIONAL
            assert job.triggered_by == "user"
            assert job.triggered_by_id == 123
            
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_start_sync_integration_not_found(self, sync_service, mock_db, sample_sync_request):
        """Test error when POS integration is not found"""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(ValueError, match="POS integration .* not found"):
            await sync_service.start_sync(sample_sync_request)

    @pytest.mark.asyncio
    async def test_start_sync_disabled(self, sync_service, mock_db, sample_pos_integration, 
                                     sample_sync_request):
        """Test error when sync is disabled"""
        disabled_config = Mock(spec=MenuSyncConfig)
        disabled_config.sync_enabled = False
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            sample_pos_integration,
            disabled_config
        ]
        
        with pytest.raises(ValueError, match="Menu sync is not enabled"):
            await sync_service.start_sync(sample_sync_request)

    @pytest.mark.asyncio
    async def test_start_sync_max_concurrent_jobs(self, sync_service, mock_db, 
                                                sample_pos_integration, sample_sync_config, 
                                                sample_sync_request):
        """Test error when max concurrent jobs exceeded"""
        sample_sync_config.max_concurrent_jobs = 1
        
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            sample_pos_integration,
            sample_sync_config
        ]
        mock_db.query.return_value.filter.return_value.count.return_value = 2  # Too many active jobs
        
        with pytest.raises(ValueError, match="Maximum concurrent sync jobs exceeded"):
            await sync_service.start_sync(sample_sync_request)

    @pytest.mark.asyncio
    async def test_execute_sync_job_success(self, sync_service, mock_db):
        """Test successful sync job execution"""
        # Create mock sync job
        sync_job = Mock(spec=MenuSyncJob)
        sync_job.id = 1
        sync_job.pos_integration_id = 1
        sync_job.sync_direction = SyncDirection.PUSH
        sync_job.status = SyncStatus.PENDING
        sync_job.retry_count = 0
        sync_job.max_retries = 3
        
        # Mock POS integration and adapter
        pos_integration = Mock(spec=POSIntegration)
        pos_integration.vendor = "square"
        pos_integration.credentials = {"access_token": "test_token"}
        
        mock_db.query.return_value.get.return_value = pos_integration
        
        with patch.object(sync_service, 'get_pos_adapter') as mock_get_adapter, \
             patch.object(sync_service, '_push_to_pos', new_callable=AsyncMock) as mock_push, \
             patch.object(sync_service, '_update_sync_statistics', new_callable=AsyncMock):
            
            mock_adapter = AsyncMock()
            mock_adapter.test_connection.return_value = True
            mock_get_adapter.return_value = mock_adapter
            
            await sync_service._execute_sync_job(sync_job)
            
            assert sync_job.status == SyncStatus.SUCCESS
            assert sync_job.started_at is not None
            assert sync_job.completed_at is not None
            mock_push.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_sync_job_connection_failure(self, sync_service, mock_db):
        """Test sync job execution with connection failure"""
        sync_job = Mock(spec=MenuSyncJob)
        sync_job.id = 1
        sync_job.pos_integration_id = 1
        sync_job.sync_direction = SyncDirection.PUSH
        sync_job.status = SyncStatus.PENDING
        sync_job.retry_count = 0
        sync_job.max_retries = 3
        
        pos_integration = Mock(spec=POSIntegration)
        mock_db.query.return_value.get.return_value = pos_integration
        
        with patch.object(sync_service, 'get_pos_adapter') as mock_get_adapter, \
             patch.object(sync_service, '_update_sync_statistics', new_callable=AsyncMock):
            
            mock_adapter = AsyncMock()
            mock_adapter.test_connection.return_value = False
            mock_get_adapter.return_value = mock_adapter
            
            await sync_service._execute_sync_job(sync_job)
            
            assert sync_job.status == SyncStatus.ERROR
            assert "Failed to connect to POS system" in sync_job.error_message

    def test_calculate_entity_hash(self, sync_service):
        """Test entity hash calculation"""
        entity_data = {
            "name": "Test Item",
            "price": 10.99,
            "id": 123,
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-02T00:00:00Z"
        }
        
        hash1 = sync_service._calculate_entity_hash(entity_data)
        
        # Hash should be consistent
        hash2 = sync_service._calculate_entity_hash(entity_data)
        assert hash1 == hash2
        
        # Hash should ignore timestamps and IDs
        entity_data_modified = entity_data.copy()
        entity_data_modified["updated_at"] = "2023-01-03T00:00:00Z"  # Different timestamp
        entity_data_modified["id"] = 456  # Different ID
        
        hash3 = sync_service._calculate_entity_hash(entity_data_modified)
        assert hash1 == hash3  # Should be same since content unchanged
        
        # Hash should change with content
        entity_data_modified["name"] = "Different Item"
        hash4 = sync_service._calculate_entity_hash(entity_data_modified)
        assert hash1 != hash4

    @pytest.mark.asyncio
    async def test_sync_entity_bidirectional_no_changes(self, sync_service, mock_db):
        """Test bidirectional sync when no changes detected"""
        sync_job = Mock(spec=MenuSyncJob)
        mapping = Mock(spec=POSMenuMapping)
        mapping.entity_type = "category"
        mapping.aura_entity_id = 1
        mapping.pos_entity_id = "pos_123"
        mapping.sync_hash = "test_hash"
        
        ctx = {"sync_job": sync_job}
        
        with patch.object(sync_service, '_get_aura_entity_data', new_callable=AsyncMock) as mock_aura, \
             patch.object(sync_service, '_get_pos_entity_data', new_callable=AsyncMock) as mock_pos, \
             patch.object(sync_service, '_calculate_entity_hash') as mock_hash, \
             patch.object(sync_service, '_log_sync_operation', new_callable=AsyncMock) as mock_log:
            
            mock_aura.return_value = {"name": "Test Category"}
            mock_pos.return_value = {"name": "Test Category"}
            mock_hash.return_value = "test_hash"  # Same hash = no changes
            
            await sync_service._sync_entity_bidirectional(sync_job, Mock(), mapping, ctx)
            
            mock_log.assert_called_once()
            # Verify it logged "no_change" operation
            args, kwargs = mock_log.call_args
            assert args[2] == "no_change"  # operation parameter

    @pytest.mark.asyncio
    async def test_sync_entity_bidirectional_conflict(self, sync_service, mock_db):
        """Test bidirectional sync with conflict detection"""
        sync_job = Mock(spec=MenuSyncJob)
        sync_job.conflicts_detected = 0
        
        mapping = Mock(spec=POSMenuMapping)
        mapping.entity_type = "item"
        mapping.aura_entity_id = 1
        mapping.pos_entity_id = "pos_123"
        mapping.sync_hash = "old_hash"
        mapping.conflict_resolution = ConflictResolution.MANUAL
        
        ctx = {"sync_job": sync_job}
        
        aura_data = {"name": "Item A", "price": 10.99}
        pos_data = {"name": "Item A", "price": 12.99}  # Price conflict
        
        with patch.object(sync_service, '_get_aura_entity_data', new_callable=AsyncMock) as mock_aura, \
             patch.object(sync_service, '_get_pos_entity_data', new_callable=AsyncMock) as mock_pos, \
             patch.object(sync_service, '_calculate_entity_hash') as mock_hash, \
             patch.object(sync_service, '_handle_sync_conflict', new_callable=AsyncMock) as mock_conflict:
            
            mock_aura.return_value = aura_data
            mock_pos.return_value = pos_data
            mock_hash.side_effect = ["new_hash_aura", "new_hash_pos"]  # Both changed
            
            await sync_service._sync_entity_bidirectional(sync_job, Mock(), mapping, ctx)
            
            mock_conflict.assert_called_once_with(sync_job, mapping, aura_data, pos_data, ctx)

    def test_detect_conflicting_fields(self, sync_service):
        """Test conflict field detection"""
        aura_data = {
            "name": "Test Item",
            "price": 10.99,
            "description": "A test item",
            "is_active": True
        }
        
        pos_data = {
            "name": "Test Item",
            "price": 12.99,  # Different price
            "description": "Updated description",  # Different description
            "is_active": True
        }
        
        conflicting_fields = sync_service._detect_conflicting_fields(aura_data, pos_data)
        
        assert "price" in conflicting_fields
        assert "description" in conflicting_fields
        assert "name" not in conflicting_fields
        assert "is_active" not in conflicting_fields

    def test_calculate_conflict_priority(self, sync_service):
        """Test conflict priority calculation"""
        # Price conflict should have high priority
        aura_data = {"price": 10.99, "is_available": True}
        pos_data = {"price": 12.99, "is_available": True}
        
        priority = sync_service._calculate_conflict_priority(aura_data, pos_data)
        assert priority == 8  # High priority for price conflict
        
        # Availability conflict should have medium-high priority
        aura_data = {"price": 10.99, "is_available": True}
        pos_data = {"price": 10.99, "is_available": False}
        
        priority = sync_service._calculate_conflict_priority(aura_data, pos_data)
        assert priority == 7  # Medium-high priority for availability conflict
        
        # No critical conflicts should have default priority
        aura_data = {"name": "Item A", "description": "Desc A"}
        pos_data = {"name": "Item B", "description": "Desc B"}
        
        priority = sync_service._calculate_conflict_priority(aura_data, pos_data)
        assert priority == 5  # Default priority

    def test_calculate_conflict_severity(self, sync_service):
        """Test conflict severity calculation"""
        # Price conflict should be high severity
        aura_data = {"price": 10.99}
        pos_data = {"price": 12.99}
        
        severity = sync_service._calculate_conflict_severity(aura_data, pos_data)
        assert severity == "high"
        
        # Availability conflict should be medium severity
        aura_data = {"is_available": True}
        pos_data = {"is_available": False}
        
        severity = sync_service._calculate_conflict_severity(aura_data, pos_data)
        assert severity == "medium"
        
        # Other conflicts should be low severity
        aura_data = {"name": "Item A"}
        pos_data = {"name": "Item B"}
        
        severity = sync_service._calculate_conflict_severity(aura_data, pos_data)
        assert severity == "low"

    @pytest.mark.asyncio
    async def test_get_sync_status_existing_job(self, sync_service, mock_db):
        """Test getting sync status for existing job"""
        job_id = "test-job-uuid"
        
        mock_job = Mock(spec=MenuSyncJob)
        mock_job.job_id = job_id
        mock_job.status = SyncStatus.IN_PROGRESS
        mock_job.processed_entities = 50
        mock_job.total_entities = 100
        mock_job.conflicts_detected = 2
        mock_job.failed_entities = 1
        mock_job.started_at = datetime.utcnow() - timedelta(minutes=5)
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_job
        
        status_response = await sync_service.get_sync_status(job_id)
        
        assert status_response is not None
        assert status_response.job_id == job_id
        assert status_response.status == SyncStatus.IN_PROGRESS
        assert status_response.progress["processed"] == 50
        assert status_response.progress["total"] == 100
        assert status_response.progress["conflicts"] == 2
        assert status_response.progress["errors"] == 1

    @pytest.mark.asyncio
    async def test_get_sync_status_nonexistent_job(self, sync_service, mock_db):
        """Test getting sync status for non-existent job"""
        job_id = "nonexistent-job-uuid"
        
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        status_response = await sync_service.get_sync_status(job_id)
        
        assert status_response is None

    def test_generate_version_name(self, sync_service):
        """Test version name generation"""
        mock_config = Mock()
        mock_config.version_name_template = "{operation}_{timestamp}_{vendor}"
        mock_config.pos_integration = Mock()
        mock_config.pos_integration.vendor = "square"
        
        with patch('backend.core.menu_sync_service.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value.strftime.return_value = "20231201_120000"
            
            version_name = sync_service._generate_version_name(mock_config, "POS_PULL")
            
            assert "POS_PULL" in version_name
            assert "20231201_120000" in version_name
            assert "square" in version_name

    @pytest.mark.asyncio
    async def test_delayed_retry(self, sync_service):
        """Test delayed retry mechanism"""
        sync_job = Mock(spec=MenuSyncJob)
        
        with patch.object(sync_service, '_execute_sync_job', new_callable=AsyncMock) as mock_execute, \
             patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            
            await sync_service._delayed_retry(sync_job, delay_seconds=60)
            
            mock_sleep.assert_called_once_with(60)
            mock_execute.assert_called_once_with(sync_job)

    def test_sync_context_manager(self, sync_service):
        """Test sync context manager"""
        sync_job = Mock(spec=MenuSyncJob)
        version_id = 123
        
        with sync_service._sync_context(sync_job, version_id) as ctx:
            assert ctx['sync_job'] == sync_job
            assert ctx['version_id'] == version_id
            assert 'start_time' in ctx
            assert isinstance(ctx['start_time'], datetime)

    @pytest.mark.asyncio
    async def test_log_sync_operation(self, sync_service, mock_db):
        """Test sync operation logging"""
        sync_job = Mock(spec=MenuSyncJob)
        sync_job.id = 1
        
        mapping = Mock(spec=POSMenuMapping)
        mapping.id = 2
        mapping.entity_type = "item"
        mapping.aura_entity_id = 100
        mapping.pos_entity_id = "pos_200"
        
        ctx = {
            'sync_job': sync_job,
            'version_id': 5,
            'start_time': datetime.utcnow() - timedelta(milliseconds=500)
        }
        
        sync_log = await sync_service._log_sync_operation(
            sync_job, mapping, "update", SyncDirection.PUSH, 
            SyncStatus.SUCCESS, ctx, 
            aura_data_before={"name": "Old Name"},
            aura_data_after={"name": "New Name"}
        )
        
        assert isinstance(sync_log, MenuSyncLog)
        assert sync_log.sync_job_id == 1
        assert sync_log.mapping_id == 2
        assert sync_log.entity_type == "item"
        assert sync_log.operation == "update"
        assert sync_log.sync_direction == SyncDirection.PUSH
        assert sync_log.status == SyncStatus.SUCCESS
        assert sync_log.menu_version_id == 5
        assert sync_log.processing_time_ms >= 500
        
        mock_db.add.assert_called_once_with(sync_log)
        mock_db.flush.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])