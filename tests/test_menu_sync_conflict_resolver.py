# tests/test_menu_sync_conflict_resolver.py

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.core.menu_sync_conflict_resolver import MenuSyncConflictResolver
from backend.core.menu_sync_models import (
    MenuSyncConflict, MenuSyncJob, ConflictResolution, SyncDirection
)
from backend.core.menu_sync_schemas import MenuSyncConflictResolve
from backend.core.menu_models import MenuCategory, MenuItem, ModifierGroup, Modifier


class TestMenuSyncConflictResolver:
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def conflict_resolver(self, mock_db):
        """Create MenuSyncConflictResolver with mocked dependencies"""
        return MenuSyncConflictResolver(mock_db)
    
    @pytest.fixture
    def sample_conflict(self):
        """Sample conflict for testing"""
        conflict = Mock(spec=MenuSyncConflict)
        conflict.id = 1
        conflict.status = "unresolved"
        conflict.entity_type = "item"
        conflict.aura_entity_id = 100
        conflict.pos_entity_id = "pos_200"
        conflict.conflict_type = "data_mismatch"
        conflict.severity = "medium"
        conflict.priority = 5
        conflict.aura_current_data = {
            "name": "Test Item",
            "price": 10.99,
            "is_available": True,
            "updated_at": "2023-12-01T10:00:00Z"
        }
        conflict.pos_current_data = {
            "name": "Test Item",
            "price": 12.99,
            "is_available": True,
            "updated_at": "2023-12-01T09:00:00Z"
        }
        conflict.conflicting_fields = ["price"]
        conflict.created_at = datetime.utcnow() - timedelta(hours=1)
        return conflict

    def test_get_pending_conflicts_all(self, conflict_resolver, mock_db):
        """Test getting all pending conflicts"""
        mock_conflicts = [Mock(), Mock(), Mock()]
        
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value.order_by.return_value.all.return_value = mock_conflicts
        
        conflicts = conflict_resolver.get_pending_conflicts()
        
        assert len(conflicts) == 3
        mock_db.query.assert_called_once_with(MenuSyncConflict)

    def test_get_pending_conflicts_filtered(self, conflict_resolver, mock_db):
        """Test getting pending conflicts filtered by POS integration"""
        pos_integration_id = 123
        mock_conflicts = [Mock(), Mock()]
        
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value.order_by.return_value.all.return_value = mock_conflicts
        
        conflicts = conflict_resolver.get_pending_conflicts(pos_integration_id)
        
        assert len(conflicts) == 2
        # Verify the query was joined and filtered correctly
        mock_query.filter.assert_called()
        mock_query.join.assert_called()

    def test_get_conflict_summary(self, conflict_resolver, mock_db):
        """Test getting conflict summary statistics"""
        # Mock the various query results
        mock_db.query.return_value.count.return_value = 10  # total conflicts
        mock_db.query.return_value.filter.return_value.count.return_value = 5  # unresolved
        
        # Mock entity type grouping
        mock_db.query.return_value.filter.return_value.with_entities.return_value.group_by.return_value.all.side_effect = [
            [("item", 3), ("category", 2)],  # by entity type
            [("high", 1), ("medium", 3), ("low", 1)],  # by severity
            [("data_mismatch", 4), ("deleted_entity", 1)]  # by conflict type
        ]
        
        # Mock oldest conflict
        oldest_conflict = Mock()
        oldest_conflict.created_at = datetime.utcnow() - timedelta(days=5)
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = oldest_conflict
        
        summary = conflict_resolver.get_conflict_summary()
        
        assert summary["total_conflicts"] == 10
        assert summary["unresolved_conflicts"] == 5
        assert summary["by_entity_type"] == {"item": 3, "category": 2}
        assert summary["by_severity"] == {"high": 1, "medium": 3, "low": 1}
        assert summary["by_conflict_type"] == {"data_mismatch": 4, "deleted_entity": 1}
        assert summary["oldest_conflict"] is not None

    def test_resolve_conflict_success(self, conflict_resolver, mock_db, sample_conflict):
        """Test successful conflict resolution"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_conflict
        
        resolution = MenuSyncConflictResolve(
            resolution_strategy=ConflictResolution.AURA_WINS,
            resolution_notes="User selected AuraConnect data"
        )
        
        with patch.object(conflict_resolver, '_resolve_aura_wins', return_value=True) as mock_resolve:
            result = conflict_resolver.resolve_conflict(1, resolution, user_id=456)
            
            assert result is True
            assert sample_conflict.status == "resolved"
            assert sample_conflict.resolution_strategy == ConflictResolution.AURA_WINS
            assert sample_conflict.resolved_by == 456
            assert sample_conflict.resolved_at is not None
            assert sample_conflict.resolution_notes == "User selected AuraConnect data"
            
            mock_resolve.assert_called_once_with(sample_conflict, resolution, 456)
            mock_db.commit.assert_called_once()

    def test_resolve_conflict_not_found(self, conflict_resolver, mock_db):
        """Test resolving non-existent conflict"""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        resolution = MenuSyncConflictResolve(
            resolution_strategy=ConflictResolution.AURA_WINS
        )
        
        result = conflict_resolver.resolve_conflict(999, resolution)
        
        assert result is False

    def test_resolve_conflict_already_resolved(self, conflict_resolver, mock_db, sample_conflict):
        """Test resolving already resolved conflict"""
        sample_conflict.status = "resolved"
        mock_db.query.return_value.filter.return_value.first.return_value = sample_conflict
        
        resolution = MenuSyncConflictResolve(
            resolution_strategy=ConflictResolution.AURA_WINS
        )
        
        result = conflict_resolver.resolve_conflict(1, resolution)
        
        assert result is False

    def test_resolve_conflict_unknown_strategy(self, conflict_resolver, mock_db, sample_conflict):
        """Test resolving conflict with unknown strategy"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_conflict
        
        # Create a resolution with an invalid strategy
        resolution = MenuSyncConflictResolve(
            resolution_strategy="invalid_strategy"
        )
        
        with patch.object(conflict_resolver.resolution_strategies, 'get', return_value=None):
            result = conflict_resolver.resolve_conflict(1, resolution)
            
            assert result is False
            mock_db.rollback.assert_called_once()

    def test_auto_resolve_conflicts(self, conflict_resolver, mock_db):
        """Test automatic conflict resolution"""
        # Create mock auto-resolvable conflicts
        conflict1 = Mock(spec=MenuSyncConflict)
        conflict1.id = 1
        conflict1.status = "unresolved"
        conflict1.auto_resolvable = True
        conflict1.resolution_strategy = ConflictResolution.LATEST_WINS
        
        conflict2 = Mock(spec=MenuSyncConflict)
        conflict2.id = 2
        conflict2.status = "unresolved"
        conflict2.auto_resolvable = True
        conflict2.resolution_strategy = ConflictResolution.POS_WINS
        
        mock_query = mock_db.query.return_value
        mock_query.filter.return_value.limit.return_value.all.return_value = [conflict1, conflict2]
        
        with patch.object(conflict_resolver, 'resolve_conflict') as mock_resolve:
            mock_resolve.side_effect = [True, False]  # First succeeds, second fails
            
            result = conflict_resolver.auto_resolve_conflicts()
            
            assert result["resolved"] == 1
            assert result["failed"] == 1
            assert result["total_processed"] == 2
            assert mock_resolve.call_count == 2

    def test_ignore_conflict(self, conflict_resolver, mock_db, sample_conflict):
        """Test ignoring a conflict"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_conflict
        
        result = conflict_resolver.ignore_conflict(1, user_id=789, reason="Not important")
        
        assert result is True
        assert sample_conflict.status == "ignored"
        assert sample_conflict.resolved_by == 789
        assert sample_conflict.resolved_at is not None
        assert "Not important" in sample_conflict.resolution_notes
        mock_db.commit.assert_called_once()

    def test_reopen_conflict(self, conflict_resolver, mock_db, sample_conflict):
        """Test reopening a resolved conflict"""
        sample_conflict.status = "resolved"
        sample_conflict.resolved_by = 123
        sample_conflict.resolved_at = datetime.utcnow()
        
        mock_db.query.return_value.filter.return_value.first.return_value = sample_conflict
        
        result = conflict_resolver.reopen_conflict(1, user_id=456, reason="Need review")
        
        assert result is True
        assert sample_conflict.status == "unresolved"
        assert sample_conflict.resolution_strategy is None
        assert sample_conflict.resolved_by is None
        assert sample_conflict.resolved_at is None
        assert "Reopened by user: Need review" in sample_conflict.resolution_notes
        mock_db.commit.assert_called_once()

    def test_resolve_aura_wins(self, conflict_resolver, sample_conflict):
        """Test AURA_WINS resolution strategy"""
        resolution = MenuSyncConflictResolve(
            resolution_strategy=ConflictResolution.AURA_WINS
        )
        
        with patch.object(conflict_resolver, '_apply_data_to_pos', return_value=True) as mock_apply:
            result = conflict_resolver._resolve_aura_wins(sample_conflict, resolution, 123)
            
            assert result is True
            mock_apply.assert_called_once_with(sample_conflict, sample_conflict.aura_current_data)

    def test_resolve_pos_wins(self, conflict_resolver, sample_conflict):
        """Test POS_WINS resolution strategy"""
        resolution = MenuSyncConflictResolve(
            resolution_strategy=ConflictResolution.POS_WINS
        )
        
        with patch.object(conflict_resolver, '_apply_data_to_aura', return_value=True) as mock_apply:
            result = conflict_resolver._resolve_pos_wins(sample_conflict, resolution, 123)
            
            assert result is True
            mock_apply.assert_called_once_with(sample_conflict, sample_conflict.pos_current_data)

    def test_resolve_latest_wins_aura_newer(self, conflict_resolver, sample_conflict):
        """Test LATEST_WINS strategy with AuraConnect data being newer"""
        # AuraConnect data is newer (10:00 vs 09:00)
        resolution = MenuSyncConflictResolve(
            resolution_strategy=ConflictResolution.LATEST_WINS
        )
        
        with patch.object(conflict_resolver, '_extract_timestamp') as mock_extract, \
             patch.object(conflict_resolver, '_apply_data_to_pos', return_value=True) as mock_apply:
            
            aura_time = datetime.fromisoformat("2023-12-01T10:00:00+00:00")
            pos_time = datetime.fromisoformat("2023-12-01T09:00:00+00:00")
            mock_extract.side_effect = [aura_time, pos_time]
            
            result = conflict_resolver._resolve_latest_wins(sample_conflict, resolution, 123)
            
            assert result is True
            mock_apply.assert_called_once_with(sample_conflict, sample_conflict.aura_current_data)

    def test_resolve_latest_wins_pos_newer(self, conflict_resolver, sample_conflict):
        """Test LATEST_WINS strategy with POS data being newer"""
        resolution = MenuSyncConflictResolve(
            resolution_strategy=ConflictResolution.LATEST_WINS
        )
        
        with patch.object(conflict_resolver, '_extract_timestamp') as mock_extract, \
             patch.object(conflict_resolver, '_apply_data_to_aura', return_value=True) as mock_apply:
            
            aura_time = datetime.fromisoformat("2023-12-01T09:00:00+00:00")
            pos_time = datetime.fromisoformat("2023-12-01T10:00:00+00:00")
            mock_extract.side_effect = [aura_time, pos_time]
            
            result = conflict_resolver._resolve_latest_wins(sample_conflict, resolution, 123)
            
            assert result is True
            mock_apply.assert_called_once_with(sample_conflict, sample_conflict.pos_current_data)

    def test_apply_data_to_aura_category(self, conflict_resolver, mock_db, sample_conflict):
        """Test applying POS data to AuraConnect category"""
        sample_conflict.entity_type = "category"
        sample_conflict.aura_entity_id = 100
        
        mock_category = Mock(spec=MenuCategory)
        mock_db.query.return_value.get.return_value = mock_category
        
        pos_data = {
            "name": "Updated Category",
            "description": "New description",
            "is_active": False
        }
        
        with patch.object(conflict_resolver, '_update_category_from_pos_data') as mock_update:
            result = conflict_resolver._apply_data_to_aura(sample_conflict, pos_data)
            
            assert result is True
            mock_update.assert_called_once_with(mock_category, pos_data)
            mock_db.commit.assert_called_once()

    def test_apply_data_to_aura_item(self, conflict_resolver, mock_db, sample_conflict):
        """Test applying POS data to AuraConnect item"""
        sample_conflict.entity_type = "item"
        sample_conflict.aura_entity_id = 200
        
        mock_item = Mock(spec=MenuItem)
        mock_db.query.return_value.get.return_value = mock_item
        
        pos_data = {
            "name": "Updated Item",
            "price": 15.99,
            "is_available": False
        }
        
        with patch.object(conflict_resolver, '_update_item_from_pos_data') as mock_update:
            result = conflict_resolver._apply_data_to_aura(sample_conflict, pos_data)
            
            assert result is True
            mock_update.assert_called_once_with(mock_item, pos_data)

    def test_update_category_from_pos_data(self, conflict_resolver):
        """Test updating category with POS data"""
        mock_category = Mock(spec=MenuCategory)
        
        pos_data = {
            "name": "New Category Name",
            "description": "New description",
            "is_active": False
        }
        
        conflict_resolver._update_category_from_pos_data(mock_category, pos_data)
        
        assert mock_category.name == "New Category Name"
        assert mock_category.description == "New description"
        assert mock_category.is_active is False

    def test_update_item_from_pos_data(self, conflict_resolver):
        """Test updating item with POS data"""
        mock_item = Mock(spec=MenuItem)
        
        pos_data = {
            "name": "New Item Name",
            "description": "New description",
            "price": 25.99,
            "is_active": True,
            "is_available": False
        }
        
        conflict_resolver._update_item_from_pos_data(mock_item, pos_data)
        
        assert mock_item.name == "New Item Name"
        assert mock_item.description == "New description"
        assert mock_item.price == 25.99
        assert mock_item.is_active is True
        assert mock_item.is_available is False

    def test_extract_timestamp_datetime_object(self, conflict_resolver):
        """Test extracting timestamp from datetime object"""
        test_time = datetime.utcnow()
        data = {"updated_at": test_time}
        
        result = conflict_resolver._extract_timestamp(data)
        
        assert result == test_time

    def test_extract_timestamp_iso_string(self, conflict_resolver):
        """Test extracting timestamp from ISO string"""
        data = {"updated_at": "2023-12-01T10:00:00Z"}
        
        result = conflict_resolver._extract_timestamp(data)
        
        assert isinstance(result, datetime)
        assert result.year == 2023
        assert result.month == 12
        assert result.day == 1

    def test_extract_timestamp_not_found(self, conflict_resolver):
        """Test extracting timestamp when none exists"""
        data = {"name": "Test Item", "price": 10.99}
        
        result = conflict_resolver._extract_timestamp(data)
        
        assert result is None

    def test_extract_timestamp_empty_data(self, conflict_resolver):
        """Test extracting timestamp from empty data"""
        result = conflict_resolver._extract_timestamp(None)
        assert result is None
        
        result = conflict_resolver._extract_timestamp({})
        assert result is None

    def test_get_conflict_recommendations_high_priority(self, conflict_resolver, sample_conflict):
        """Test getting recommendations for high priority conflict"""
        sample_conflict.severity = "high"
        sample_conflict.conflicting_fields = ["price"]
        sample_conflict.conflict_type = "data_mismatch"
        
        with patch.object(conflict_resolver, '_extract_timestamp', return_value=None):
            recommendations = conflict_resolver.get_conflict_recommendations(sample_conflict)
            
            assert "High priority conflict - immediate attention required" in recommendations
            assert "Price conflict detected - verify with management before resolving" in recommendations

    def test_get_conflict_recommendations_availability_conflict(self, conflict_resolver, sample_conflict):
        """Test getting recommendations for availability conflict"""
        sample_conflict.conflicting_fields = ["is_available"]
        
        with patch.object(conflict_resolver, '_extract_timestamp', return_value=None):
            recommendations = conflict_resolver.get_conflict_recommendations(sample_conflict)
            
            assert "Availability conflict - check inventory levels" in recommendations

    def test_get_conflict_recommendations_deleted_entity(self, conflict_resolver, sample_conflict):
        """Test getting recommendations for deleted entity conflict"""
        sample_conflict.conflict_type = "deleted_entity"
        
        with patch.object(conflict_resolver, '_extract_timestamp', return_value=None):
            recommendations = conflict_resolver.get_conflict_recommendations(sample_conflict)
            
            assert "Entity deletion conflict - confirm if item should be removed" in recommendations

    def test_get_conflict_recommendations_timestamp_based(self, conflict_resolver, sample_conflict):
        """Test getting timestamp-based recommendations"""
        aura_time = datetime.utcnow()
        pos_time = aura_time - timedelta(hours=1)  # POS data is older
        
        with patch.object(conflict_resolver, '_extract_timestamp') as mock_extract:
            mock_extract.side_effect = [aura_time, pos_time]
            
            recommendations = conflict_resolver.get_conflict_recommendations(sample_conflict)
            
            assert "AuraConnect data is more recent - consider AURA_WINS strategy" in recommendations


if __name__ == "__main__":
    pytest.main([__file__])