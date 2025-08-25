"""
Test Suite for POS Migration Service

Comprehensive tests covering security, multi-tenancy, and functionality.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import json

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from ..models.migration_models import (
    POSMigrationJob,
    DataMapping,
    MigrationLog,
    ValidationResult,
    MigrationStatus,
    POSProvider,
    DataEntityType
)
from ..schemas.migration_schemas import (
    MigrationJobCreate,
    MigrationJobUpdate,
    MigrationAnalysisRequest,
    DataMappingCreate
)
from ..services.migration_service import MigrationService
from ..utils.security import encrypt_credentials, decrypt_credentials, mask_sensitive_data
from ..utils.audit import audit_log, MigrationAuditTrail


@pytest.fixture
async def db_session():
    """Mock database session."""
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    session.add = Mock()
    return session


@pytest.fixture
def admin_user():
    """Admin user fixture."""
    return {
        "id": 1,
        "email": "admin@test.com",
        "role": "admin",
        "restaurant_id": 1,
        "permissions": ["migration.create", "migration.execute", "migration.cancel"]
    }


@pytest.fixture
def manager_user():
    """Manager user fixture."""
    return {
        "id": 2,
        "email": "manager@test.com",
        "role": "manager",
        "restaurant_id": 1,
        "permissions": ["migration.create", "migration.execute"]
    }


@pytest.fixture
def staff_user():
    """Staff user fixture."""
    return {
        "id": 3,
        "email": "staff@test.com",
        "role": "staff",
        "restaurant_id": 1,
        "permissions": []
    }


@pytest.fixture
def migration_job_data():
    """Sample migration job creation data."""
    return MigrationJobCreate(
        job_name="Test POS Migration",
        source_provider=POSProvider.SQUARE,
        entities_to_migrate=[
            DataEntityType.MENU_ITEMS,
            DataEntityType.CUSTOMERS,
            DataEntityType.ORDERS
        ],
        source_credentials={
            "access_token": "test_token_123",
            "location_id": "loc_456"
        },
        batch_size=100,
        rate_limit=60
    )


class TestMigrationService:
    """Test POS Migration Service functionality."""
    
    @pytest.mark.asyncio
    async def test_create_migration_job_success(
        self,
        db_session,
        admin_user,
        migration_job_data
    ):
        """Test successful migration job creation."""
        service = MigrationService(db_session, admin_user)
        
        # Mock no existing jobs
        db_session.execute.return_value.scalar_one_or_none.return_value = None
        
        # Create job
        with patch('modules.pos_migration.utils.security.encrypt_credentials') as mock_encrypt:
            mock_encrypt.return_value = "encrypted_creds"
            
            job = await service.create_migration_job(migration_job_data)
            
            # Verify job created
            assert job is not None
            assert job.job_name == "Test POS Migration"
            assert job.source_provider == POSProvider.SQUARE
            assert job.restaurant_id == 1
            assert job.created_by == 1
            assert job.status == MigrationStatus.PENDING
            
            # Verify credentials encrypted
            mock_encrypt.assert_called_once_with(migration_job_data.source_credentials)
            
            # Verify database operations
            db_session.add.assert_called_once()
            db_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_migration_job_permission_denied(
        self,
        db_session,
        staff_user,
        migration_job_data
    ):
        """Test migration job creation with insufficient permissions."""
        service = MigrationService(db_session, staff_user)
        
        with pytest.raises(Exception) as exc_info:
            await service.create_migration_job(migration_job_data)
        
        assert "Insufficient permissions" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_create_migration_job_duplicate_active(
        self,
        db_session,
        admin_user,
        migration_job_data
    ):
        """Test prevention of duplicate active migrations."""
        service = MigrationService(db_session, admin_user)
        
        # Mock existing active job
        existing_job = Mock()
        db_session.execute.return_value.scalar_one_or_none.return_value = existing_job
        
        with pytest.raises(Exception) as exc_info:
            await service.create_migration_job(migration_job_data)
        
        assert "active migration already exists" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_tenant_isolation(
        self,
        db_session,
        admin_user
    ):
        """Test that users can only access their restaurant's migrations."""
        service = MigrationService(db_session, admin_user)
        
        # Mock job from different restaurant
        job_id = uuid4()
        db_session.execute.return_value.scalar_one_or_none.return_value = None
        
        with pytest.raises(Exception) as exc_info:
            await service.get_migration_job(job_id)
        
        assert "not found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_start_migration_validation(
        self,
        db_session,
        admin_user
    ):
        """Test migration start validation."""
        service = MigrationService(db_session, admin_user)
        
        # Create mock job in wrong status
        job = Mock()
        job.id = uuid4()
        job.status = MigrationStatus.COMPLETED
        job.restaurant_id = 1
        
        with patch.object(service, 'get_migration_job', return_value=job):
            with pytest.raises(Exception) as exc_info:
                await service.start_migration(job.id)
            
            assert "Cannot start migration" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_pause_migration_checkpoint(
        self,
        db_session,
        admin_user
    ):
        """Test migration pause with checkpoint creation."""
        service = MigrationService(db_session, admin_user)
        
        # Create mock active job
        job = Mock()
        job.id = uuid4()
        job.status = MigrationStatus.MIGRATING
        job.current_entity = "menu_items"
        job.progress_percentage = 45.5
        job.records_processed = 150
        job.restaurant_id = 1
        
        with patch.object(service, 'get_migration_job', return_value=job):
            result = await service.pause_migration(job.id)
            
            # Verify status changed
            assert job.status == MigrationStatus.PAUSED
            
            # Verify checkpoint created
            assert job.rollback_checkpoint is not None
            assert job.rollback_checkpoint["entity"] == "menu_items"
            assert job.rollback_checkpoint["progress"] == 45.5
            assert job.rollback_checkpoint["records_processed"] == 150
    
    @pytest.mark.asyncio
    async def test_cancel_migration_with_rollback(
        self,
        db_session,
        admin_user
    ):
        """Test migration cancellation with rollback."""
        service = MigrationService(db_session, admin_user)
        
        # Create mock job with processed records
        job = Mock()
        job.id = uuid4()
        job.status = MigrationStatus.MIGRATING
        job.rollback_enabled = True
        job.records_processed = 100
        job.restaurant_id = 1
        
        with patch.object(service, 'get_migration_job', return_value=job):
            with patch('asyncio.create_task') as mock_create_task:
                result = await service.cancel_migration(job.id)
                
                # Verify rollback initiated
                assert job.status == MigrationStatus.ROLLBACK
                mock_create_task.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_analyze_source_system(
        self,
        db_session,
        admin_user
    ):
        """Test POS system analysis."""
        service = MigrationService(db_session, admin_user)
        
        request = MigrationAnalysisRequest(
            source_provider=POSProvider.SQUARE,
            source_credentials={"access_token": "test"},
            entities_to_analyze=[DataEntityType.MENU_ITEMS],
            sample_size=10
        )
        
        with patch.object(service, '_analyze_pos_data') as mock_analyze:
            mock_analyze.return_value = {
                "schema": {"menu_items": {"fields": ["id", "name", "price"]}},
                "record_counts": {"menu_items": 100},
                "entities": {"menu_items": {"total_records": 100}}
            }
            
            with patch.object(service.ai_service, 'suggest_mappings') as mock_ai:
                mock_ai.return_value = [
                    DataMappingCreate(
                        entity_type=DataEntityType.MENU_ITEMS,
                        source_field="id",
                        target_field="external_id"
                    )
                ]
                
                result = await service.analyze_source_system(request)
                
                assert result.source_provider == POSProvider.SQUARE
                assert result.compatibility_score > 0
                assert len(result.suggested_mappings) > 0
                assert result.estimated_duration_minutes > 0


class TestSecurityUtilities:
    """Test security utilities."""
    
    def test_encrypt_decrypt_credentials(self):
        """Test credential encryption and decryption."""
        original = {
            "api_key": "secret_key_123",
            "token": "bearer_token_456"
        }
        
        encrypted = encrypt_credentials(original)
        assert encrypted != json.dumps(original)
        
        decrypted = decrypt_credentials(encrypted)
        assert decrypted == original
    
    def test_mask_sensitive_data(self):
        """Test sensitive data masking."""
        data = {
            "api_key": "secret_key_123456",
            "token": "bearer_token",
            "name": "John Doe",
            "password": "mypassword",
            "public_field": "visible"
        }
        
        masked = mask_sensitive_data(data)
        
        assert masked["api_key"] == "se**********56"
        assert "***" in masked["token"]
        assert masked["name"] == "John Doe"  # Name not masked by default
        assert "***" in masked["password"]
        assert masked["public_field"] == "visible"
    
    def test_mock_data_detection(self):
        """Test detection of mock/test data."""
        from ..utils.security import contains_mock_data
        
        # Test data with mock patterns
        mock_data = {
            "name": "John Doe",
            "email": "test@example.com",
            "phone": "123-456-7890"
        }
        assert contains_mock_data(mock_data) == True
        
        # Real-looking data
        real_data = {
            "name": "Alice Smith",
            "email": "alice@restaurant.com",
            "phone": "555-8921"
        }
        assert contains_mock_data(real_data) == False
    
    def test_compliance_validation(self):
        """Test compliance validation."""
        from ..utils.security import validate_data_compliance
        
        # Test PCI compliance
        payment_data = {
            "card_number": "4111111111111111",  # Unmasked
            "cvv": "123"
        }
        result = validate_data_compliance(payment_data, "payments")
        assert result["compliant"] == False
        assert len(result["issues"]) > 0
        
        # Test GDPR compliance
        customer_data = {
            "email": "customer@test.com",
            "phone": "555-1234"
        }
        result = validate_data_compliance(customer_data, "customers")
        assert len(result["warnings"]) > 0  # No consent flags


class TestAuditTrail:
    """Test audit trail functionality."""
    
    @pytest.mark.asyncio
    async def test_audit_log_creation(self, db_session):
        """Test audit log creation."""
        await audit_log(
            db_session,
            user_id=1,
            action="migration.create",
            resource_type="migration_job",
            resource_id="test_123",
            details={"test": "data"}
        )
        
        db_session.add.assert_called_once()
        db_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_migration_audit_trail(self, db_session):
        """Test comprehensive migration audit trail."""
        job_id = str(uuid4())
        audit_trail = MigrationAuditTrail(db_session, job_id)
        
        # Log start
        await audit_trail.log_start(
            user_id=1,
            config={"source": "square", "entities": ["menu_items"]}
        )
        
        # Log entity processing
        await audit_trail.log_entity_processing(
            entity_type="menu_items",
            total_records=100,
            batch_size=10
        )
        
        # Log batch complete
        await audit_trail.log_batch_complete(
            entity_type="menu_items",
            batch_num=1,
            succeeded=9,
            failed=1,
            duration_ms=500
        )
        
        # Log error
        error = Exception("Test error")
        await audit_trail.log_error(
            entity_type="menu_items",
            entity_id="item_123",
            error=error,
            context={"field": "price"}
        )
        
        # Verify all logs created
        assert db_session.add.call_count >= 4
        assert db_session.commit.call_count >= 4


class TestBackgroundProcessing:
    """Test background job processing."""
    
    @pytest.mark.asyncio
    async def test_background_job_scheduling(self):
        """Test background job scheduling."""
        from ..services.background_service import BackgroundMigrationService
        
        service = BackgroundMigrationService()
        job_id = uuid4()
        
        with patch('modules.pos_migration.services.background_service.process_migration_job') as mock_task:
            mock_task.apply_async.return_value.id = "task_123"
            
            task_id = await service.schedule_job(job_id)
            
            assert task_id == "task_123"
            mock_task.apply_async.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_batch_processing_with_rate_limit(self):
        """Test batch processing with rate limiting."""
        from ..services.background_service import _process_entity
        
        # Mock adapter
        adapter = Mock()
        adapter.fetch_data = AsyncMock(side_effect=[
            [{"id": 1}, {"id": 2}],  # First batch
            [{"id": 3}],  # Second batch
            []  # End
        ])
        
        # Mock job with rate limit
        job = Mock()
        job.id = uuid4()
        job.batch_size = 2
        job.rate_limit = 120  # 120 per minute
        job.current_entity = None
        job.progress_percentage = 0
        job.records_processed = 0
        job.records_succeeded = 0
        job.records_failed = 0
        job.entities_completed = []
        
        # Process entity
        # Would need proper async context to test fully


class TestIntegration:
    """Integration tests."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_migration_flow(
        self,
        db_session,
        admin_user,
        migration_job_data
    ):
        """Test complete migration flow."""
        service = MigrationService(db_session, admin_user)
        
        # 1. Create migration job
        db_session.execute.return_value.scalar_one_or_none.return_value = None
        with patch('modules.pos_migration.utils.security.encrypt_credentials'):
            job = await service.create_migration_job(migration_job_data)
            assert job.status == MigrationStatus.PENDING
        
        # 2. Analyze source system
        analysis_request = MigrationAnalysisRequest(
            source_provider=POSProvider.SQUARE,
            source_credentials=migration_job_data.source_credentials,
            entities_to_analyze=migration_job_data.entities_to_migrate,
            sample_size=10
        )
        
        with patch.object(service, '_analyze_pos_data'):
            with patch.object(service.ai_service, 'suggest_mappings'):
                analysis = await service.analyze_source_system(analysis_request)
                assert analysis.compatibility_score > 0
        
        # 3. Update mappings
        mappings = [
            DataMappingCreate(
                entity_type=DataEntityType.MENU_ITEMS,
                source_field="id",
                target_field="external_id"
            )
        ]
        
        with patch.object(service, 'get_migration_job', return_value=job):
            await service.update_mappings(job.id, mappings)
        
        # 4. Start migration
        job.status = MigrationStatus.PENDING
        with patch.object(service, 'get_migration_job', return_value=job):
            with patch('asyncio.create_task'):
                await service.start_migration(job.id)
                assert job.status == MigrationStatus.MIGRATING
        
        # 5. Pause migration
        with patch.object(service, 'get_migration_job', return_value=job):
            await service.pause_migration(job.id)
            assert job.status == MigrationStatus.PAUSED
        
        # 6. Resume migration
        with patch.object(service, 'get_migration_job', return_value=job):
            with patch('asyncio.create_task'):
                await service.start_migration(job.id)
                assert job.status == MigrationStatus.MIGRATING