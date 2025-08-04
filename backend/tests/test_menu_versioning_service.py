# backend/tests/test_menu_versioning_service.py

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from core.menu_versioning_service import MenuVersioningService
from core.menu_versioning_models import (
    MenuVersion, MenuCategoryVersion, MenuItemVersion, 
    ModifierGroupVersion, MenuAuditLog, VersionType, ChangeType
)
from core.menu_versioning_schemas import (
    CreateVersionRequest, PublishVersionRequest, RollbackVersionRequest,
    VersionComparisonRequest
)
from core.menu_models import MenuCategory, MenuItem, ModifierGroup


class TestMenuVersioningService:
    """Test suite for MenuVersioningService"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def service(self, mock_db):
        """MenuVersioningService instance with mock database"""
        return MenuVersioningService(mock_db)
    
    @pytest.fixture
    def sample_version_request(self):
        """Sample version creation request"""
        return CreateVersionRequest(
            version_name="Test Version",
            description="Test version description",
            version_type=VersionType.MANUAL,
            include_inactive=False
        )
    
    @pytest.fixture
    def sample_version(self):
        """Sample menu version"""
        return MenuVersion(
            id=1,
            version_number="v20250728-001",
            version_name="Test Version",
            description="Test description",
            version_type=VersionType.MANUAL,
            is_active=False,
            is_published=False,
            created_by=1,
            total_items=5,
            total_categories=2,
            total_modifiers=3,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
    
    def test_create_version_success(self, service, mock_db, sample_version_request):
        """Test successful version creation"""
        # Mock database operations
        mock_db.add = Mock()
        mock_db.flush = Mock()
        mock_db.commit = Mock()
        mock_db.query.return_value.filter.return_value.count.return_value = 0
        
        # Mock snapshot methods
        with patch.object(service, '_snapshot_categories') as mock_categories, \
             patch.object(service, '_snapshot_items') as mock_items, \
             patch.object(service, '_snapshot_modifiers') as mock_modifiers, \
             patch.object(service, '_generate_version_number') as mock_version_num:
            
            mock_version_num.return_value = "v20250728-001"
            mock_categories.return_value = []
            mock_items.return_value = []
            mock_modifiers.return_value = []
            
            # Execute
            result = service.create_version(sample_version_request, user_id=1)
            
            # Assertions
            assert result is not None
            mock_db.add.assert_called()
            mock_db.flush.assert_called()
            mock_version_num.assert_called_once_with(VersionType.MANUAL)
            mock_categories.assert_called_once()
            mock_items.assert_called_once()
            mock_modifiers.assert_called_once()
    
    def test_generate_version_number_manual(self, service, mock_db):
        """Test version number generation for manual versions"""
        mock_db.query.return_value.filter.return_value.count.return_value = 0
        
        with patch('backend.core.menu_versioning_service.datetime') as mock_datetime:
            mock_now = Mock()
            mock_now.strftime.return_value = "20250728"
            mock_datetime.now.return_value = mock_now
            
            result = service._generate_version_number(VersionType.MANUAL)
            
            assert result.startswith("v20250728")
            assert result.endswith("-001")
    
    def test_generate_version_number_scheduled(self, service, mock_db):
        """Test version number generation for scheduled versions"""
        mock_db.query.return_value.filter.return_value.count.return_value = 2
        
        with patch('backend.core.menu_versioning_service.datetime') as mock_datetime:
            mock_now = Mock()
            mock_now.strftime.return_value = "20250728"
            mock_datetime.now.return_value = mock_now
            
            result = service._generate_version_number(VersionType.SCHEDULED)
            
            assert result.startswith("s20250728")
            assert result.endswith("-003")  # Count + 1
    
    def test_publish_version_success(self, service, mock_db, sample_version):
        """Test successful version publishing"""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            sample_version,  # Target version
            None  # No current active version
        ]
        
        with patch.object(service, '_apply_version_to_live_menu') as mock_apply:
            request = PublishVersionRequest(force=False)
            
            result = service.publish_version(1, request, user_id=1)
            
            assert result.is_active is True
            assert result.is_published is True
            assert result.published_at is not None
            mock_apply.assert_called_once()
    
    def test_publish_version_already_published(self, service, mock_db, sample_version):
        """Test publishing already published version without force"""
        sample_version.is_published = True
        mock_db.query.return_value.filter.return_value.first.return_value = sample_version
        
        request = PublishVersionRequest(force=False)
        
        with pytest.raises(ValueError, match="Version is already published"):
            service.publish_version(1, request, user_id=1)
    
    def test_publish_version_force_override(self, service, mock_db, sample_version):
        """Test force publishing already published version"""
        sample_version.is_published = True
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            sample_version,  # Target version
            None  # No current active version
        ]
        
        with patch.object(service, '_apply_version_to_live_menu'):
            request = PublishVersionRequest(force=True)
            
            result = service.publish_version(1, request, user_id=1)
            
            assert result.is_active is True
            assert result.is_published is True
    
    def test_rollback_to_version_with_backup(self, service, mock_db, sample_version):
        """Test rollback with backup creation"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_version
        
        with patch.object(service, 'create_version') as mock_create, \
             patch.object(service, '_copy_version_data') as mock_copy, \
             patch.object(service, 'publish_version') as mock_publish:
            
            mock_backup = Mock()
            mock_backup.id = 999
            mock_create.return_value = mock_backup
            
            request = RollbackVersionRequest(
                target_version_id=1,
                create_backup=True,
                rollback_reason="Testing rollback"
            )
            
            result = service.rollback_to_version(request, user_id=1)
            
            assert result is not None
            mock_create.assert_called_once()  # Backup creation
            mock_copy.assert_called_once()
            mock_publish.assert_called_once()
    
    def test_rollback_to_nonexistent_version(self, service, mock_db):
        """Test rollback to non-existent version"""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        request = RollbackVersionRequest(
            target_version_id=999,
            create_backup=True,
            rollback_reason="Testing"
        )
        
        with pytest.raises(ValueError, match="Target version not found"):
            service.rollback_to_version(request, user_id=1)
    
    def test_get_versions_paginated(self, service, mock_db):
        """Test paginated version retrieval"""
        mock_versions = [Mock() for _ in range(5)]
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 25
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_versions
        
        mock_db.query.return_value = mock_query
        
        versions, total = service.get_versions(page=2, size=5)
        
        assert len(versions) == 5
        assert total == 25
        mock_query.offset.assert_called_with(5)  # (page-1) * size
        mock_query.limit.assert_called_with(5)
    
    def test_get_versions_filtered_by_type(self, service, mock_db):
        """Test version retrieval filtered by type"""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 10
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        
        mock_db.query.return_value = mock_query
        
        service.get_versions(version_type=VersionType.MANUAL)
        
        # Verify that filter was called twice (once for deleted_at, once for version_type)
        assert mock_query.filter.call_count == 2
    
    def test_get_audit_logs_paginated(self, service, mock_db):
        """Test paginated audit log retrieval"""
        mock_logs = [Mock() for _ in range(10)]
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 100
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_logs
        
        mock_db.query.return_value = mock_query
        
        logs, total = service.get_audit_logs(version_id=1, page=3, size=10)
        
        assert len(logs) == 10
        assert total == 100
        mock_query.offset.assert_called_with(20)  # (page-1) * size
        mock_query.limit.assert_called_with(10)
    
    def test_get_version_details_success(self, service, mock_db, sample_version):
        """Test successful version details retrieval"""
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            sample_version,  # Main version
            None  # Parent version (if exists)
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        
        result = service.get_version_details(1)
        
        assert result is not None
        # Verify multiple queries were made for related data
        assert mock_db.query.call_count >= 4  # version, categories, items, modifiers, audit_entries
    
    def test_get_version_details_not_found(self, service, mock_db):
        """Test version details retrieval for non-existent version"""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = service.get_version_details(999)
        
        assert result is None
    
    def test_snapshot_categories(self, service, mock_db):
        """Test category snapshotting"""
        mock_categories = [
            Mock(id=1, name="Appetizers", description="Starters", is_active=True),
            Mock(id=2, name="Mains", description="Main courses", is_active=True)
        ]
        
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_categories
        mock_db.query.return_value = mock_query
        
        audit_entries = []
        result = service._snapshot_categories(1, False, audit_entries)
        
        assert len(result) == 2
        assert mock_db.add.call_count == 2
        # Verify categories were filtered for active only
        assert mock_query.filter.call_count == 2  # deleted_at and is_active filters
    
    def test_snapshot_items(self, service, mock_db):
        """Test menu item snapshotting"""
        mock_items = [
            Mock(id=1, name="Burger", price=12.99, is_active=True),
            Mock(id=2, name="Pizza", price=15.99, is_active=True)
        ]
        
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_items
        mock_db.query.return_value = mock_query
        
        audit_entries = []
        result = service._snapshot_items(1, False, audit_entries)
        
        assert len(result) == 2
        assert mock_db.add.call_count == 2


# Integration tests for error scenarios
class TestMenuVersioningServiceIntegration:
    """Integration tests for error handling and edge cases"""
    
    def test_audit_context_rollback_on_error(self, mock_db):
        """Test that audit context properly rolls back on errors"""
        service = MenuVersioningService(mock_db)
        mock_db.commit.side_effect = Exception("DB Error")
        mock_db.rollback = Mock()
        
        with pytest.raises(Exception):
            with service.audit_context(1, "test_action") as audit_entries:
                audit_entries.append(Mock())
                # This should trigger the exception in commit
        
        mock_db.rollback.assert_called_once()
    
    def test_bulk_change_validation(self, mock_db):
        """Test bulk change validation"""
        service = MenuVersioningService(mock_db)
        
        from core.menu_versioning_schemas import BulkChangeRequest
        
        request = BulkChangeRequest(
            entity_type="invalid_type",
            entity_ids=[1, 2, 3],
            changes={"name": "Updated"},
            change_reason="Testing"
        )
        
        with pytest.raises(ValueError, match="Unsupported entity type"):
            service.bulk_change(request, user_id=1)


# Performance tests
class TestMenuVersioningServicePerformance:
    """Performance-related tests"""
    
    def test_large_version_comparison_caching(self, mock_db):
        """Test that large version comparisons are properly cached"""
        service = MenuVersioningService(mock_db)
        
        # Mock cached comparison exists
        mock_cached = Mock()
        mock_cached.comparison_data = {"summary": {"created": 10}}
        mock_db.query.return_value.filter.return_value.first.return_value = mock_cached
        
        request = VersionComparisonRequest(
            from_version_id=1,
            to_version_id=2,
            include_details=True
        )
        
        with patch('backend.core.menu_versioning_service.MenuVersionComparison.parse_obj') as mock_parse:
            mock_parse.return_value = Mock()
            
            result = service.compare_versions(request)
            
            # Should use cached result, not generate new one
            mock_parse.assert_called_once()
            assert result is not None