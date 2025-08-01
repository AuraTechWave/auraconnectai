# backend/tests/test_menu_versioning_triggers.py

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from core.menu_versioning_triggers import (
    MenuVersioningTriggers, 
    create_manual_version_on_bulk_change,
    disable_auto_versioning,
    enable_auto_versioning,
    get_change_buffer_status
)
from core.menu_models import MenuCategory, MenuItem, ModifierGroup, Modifier


class TestMenuVersioningTriggers:
    """Test suite for MenuVersioningTriggers"""
    
    @pytest.fixture
    def triggers(self):
        """Fresh triggers instance for each test"""
        return MenuVersioningTriggers()
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock()
    
    def test_initialization(self, triggers):
        """Test triggers initialization"""
        assert triggers.auto_version_threshold == 10
        assert triggers.change_buffer == []
        assert triggers.enabled is True
    
    def test_should_create_auto_version_disabled(self, triggers):
        """Test that disabled triggers don't create versions"""
        triggers.enabled = False
        
        result = triggers.should_create_auto_version(
            'price_change', 
            'menu_item', 
            {'price': 10.99}
        )
        
        assert result is False
    
    def test_should_create_auto_version_critical_changes(self, triggers):
        """Test that critical changes trigger versioning"""
        critical_changes = ['price_change', 'availability_change', 'menu_restructure']
        
        for change_type in critical_changes:
            result = triggers.should_create_auto_version(
                change_type,
                'menu_item',
                {}
            )
            assert result is True, f"Critical change {change_type} should trigger versioning"
    
    def test_should_create_auto_version_threshold_reached(self, triggers):
        """Test that version is created when buffer threshold is reached"""
        # Fill buffer to threshold
        for i in range(triggers.auto_version_threshold):
            triggers.add_change_to_buffer({
                'entity_type': 'menu_item',
                'change_type': 'update',
                'entity_id': i
            })
        
        result = triggers.should_create_auto_version(
            'update',
            'menu_item',
            {}
        )
        
        assert result is True
    
    def test_should_create_auto_version_bulk_operation(self, triggers):
        """Test that significant bulk operations trigger versioning"""
        changes = {
            'batch_operation': True,
            'affected_count': 10  # > 5, should trigger
        }
        
        result = triggers.should_create_auto_version(
            'bulk_operation',
            'multiple',
            changes
        )
        
        assert result is True
    
    def test_should_create_auto_version_small_bulk_operation(self, triggers):
        """Test that small bulk operations don't trigger versioning"""
        changes = {
            'batch_operation': True,
            'affected_count': 3  # <= 5, should not trigger
        }
        
        result = triggers.should_create_auto_version(
            'bulk_operation',
            'multiple',
            changes
        )
        
        assert result is False
    
    def test_add_change_to_buffer(self, triggers):
        """Test adding changes to buffer"""
        change_data = {
            'entity_type': 'menu_item',
            'entity_id': 1,
            'change_type': 'update'
        }
        
        triggers.add_change_to_buffer(change_data)
        
        assert len(triggers.change_buffer) == 1
        assert triggers.change_buffer[0]['entity_type'] == 'menu_item'
        assert 'timestamp' in triggers.change_buffer[0]
    
    def test_add_change_to_buffer_size_limit(self, triggers):
        """Test that buffer size is limited"""
        # Add more than 50 changes (the limit)
        for i in range(55):
            triggers.add_change_to_buffer({
                'entity_id': i,
                'change_type': 'update'
            })
        
        # Should keep only last 25
        assert len(triggers.change_buffer) == 25
        assert triggers.change_buffer[0]['entity_id'] == 30  # Should start from 30
    
    def test_summarize_changes_empty(self, triggers):
        """Test change summary with empty buffer"""
        summary = triggers._summarize_changes()
        assert summary == "No changes recorded"
    
    def test_summarize_changes_with_data(self, triggers):
        """Test change summary with data"""
        changes = [
            {'change_type': 'update', 'entity_type': 'menu_item'},
            {'change_type': 'update', 'entity_type': 'menu_item'},
            {'change_type': 'create', 'entity_type': 'category'},
            {'change_type': 'delete', 'entity_type': 'modifier'}
        ]
        
        for change in changes:
            triggers.add_change_to_buffer(change)
        
        summary = triggers._summarize_changes()
        
        assert 'Changes: 2 update, 1 create, 1 delete' in summary
        assert 'Entities: 2 menu_item, 1 category, 1 modifier' in summary
    
    @patch('backend.core.menu_versioning_triggers.MenuVersioningService')
    def test_create_auto_version_success(self, mock_service_class, triggers, mock_db):
        """Test successful auto-version creation"""
        mock_service = Mock()
        mock_version = Mock()
        mock_version.id = 123
        mock_service.create_version.return_value = mock_version
        mock_service_class.return_value = mock_service
        
        # Add some changes to buffer
        triggers.add_change_to_buffer({'change_type': 'update'})
        
        result = triggers.create_auto_version(mock_db, "Test trigger", user_id=1)
        
        assert result == 123
        assert len(triggers.change_buffer) == 0  # Buffer should be cleared
        mock_service.create_version.assert_called_once()
    
    @patch('backend.core.menu_versioning_triggers.MenuVersioningService')
    def test_create_auto_version_failure(self, mock_service_class, triggers, mock_db):
        """Test auto-version creation failure handling"""
        mock_service = Mock()
        mock_service.create_version.side_effect = Exception("DB Error")
        mock_service_class.return_value = mock_service
        
        # Mock print to capture error output
        with patch('builtins.print') as mock_print:
            result = triggers.create_auto_version(mock_db, "Test trigger")
            
            assert result is None
            mock_print.assert_called_once()
            assert "Failed to create auto-version" in mock_print.call_args[0][0]
    
    def test_category_insert_event(self, triggers):
        """Test category insertion event handling"""
        initial_buffer_size = len(triggers.change_buffer)
        
        # Mock category object
        mock_category = Mock()
        mock_category.id = 1
        mock_category.name = "Test Category"
        mock_category.description = "Test Description"
        mock_category.is_active = True
        
        # Call the event handler
        triggers._on_category_insert(None, None, mock_category)
        
        assert len(triggers.change_buffer) == initial_buffer_size + 1
        change = triggers.change_buffer[-1]
        assert change['entity_type'] == 'category'
        assert change['change_type'] == 'create'
        assert change['entity_id'] == 1
        assert change['entity_name'] == "Test Category"
    
    def test_item_update_event_price_change(self, triggers):
        """Test menu item update with price change"""
        initial_buffer_size = len(triggers.change_buffer)
        
        # Mock item with price change flag
        mock_item = Mock()
        mock_item.id = 1
        mock_item.name = "Test Item"
        mock_item.price = 15.99
        mock_item.is_active = True
        mock_item.is_available = True
        mock_item._price_changed = True  # Flag indicating price changed
        
        triggers._on_item_update(None, None, mock_item)
        
        assert len(triggers.change_buffer) == initial_buffer_size + 1
        change = triggers.change_buffer[-1]
        assert change['change_type'] == 'price_change'
        assert change['entity_type'] == 'menu_item'
    
    def test_item_update_event_availability_change(self, triggers):
        """Test menu item update with availability change"""
        initial_buffer_size = len(triggers.change_buffer)
        
        mock_item = Mock()
        mock_item.id = 1
        mock_item.name = "Test Item"
        mock_item.price = 15.99
        mock_item.is_active = True
        mock_item.is_available = False
        mock_item._availability_changed = True  # Flag indicating availability changed
        
        triggers._on_item_update(None, None, mock_item)
        
        assert len(triggers.change_buffer) == initial_buffer_size + 1
        change = triggers.change_buffer[-1]
        assert change['change_type'] == 'availability_change'
    
    def test_item_delete_event(self, triggers):
        """Test menu item deletion event"""
        initial_buffer_size = len(triggers.change_buffer)
        
        mock_item = Mock()
        mock_item.id = 1
        mock_item.name = "Deleted Item"
        mock_item.price = 12.99
        mock_item.category_id = 2
        
        triggers._on_item_delete(None, None, mock_item)
        
        assert len(triggers.change_buffer) == initial_buffer_size + 1
        change = triggers.change_buffer[-1]
        assert change['change_type'] == 'delete'
        assert change['entity_type'] == 'menu_item'
        assert change['old_values']['name'] == "Deleted Item"
    
    def test_modifier_group_events(self, triggers):
        """Test modifier group event handling"""
        mock_group = Mock()
        mock_group.id = 1
        mock_group.name = "Size Options"
        mock_group.selection_type = "single"
        mock_group.is_required = True
        mock_group.is_active = True
        
        initial_size = len(triggers.change_buffer)
        
        # Test insert
        triggers._on_modifier_group_insert(None, None, mock_group)
        assert len(triggers.change_buffer) == initial_size + 1
        assert triggers.change_buffer[-1]['change_type'] == 'create'
        
        # Test update
        triggers._on_modifier_group_update(None, None, mock_group)
        assert len(triggers.change_buffer) == initial_size + 2
        assert triggers.change_buffer[-1]['change_type'] == 'modifier_change'
        
        # Test delete
        triggers._on_modifier_group_delete(None, None, mock_group)
        assert len(triggers.change_buffer) == initial_size + 3
        assert triggers.change_buffer[-1]['change_type'] == 'delete'
    
    def test_modifier_events(self, triggers):
        """Test individual modifier event handling"""
        mock_modifier = Mock()
        mock_modifier.id = 1
        mock_modifier.name = "Large"
        mock_modifier.price_adjustment = 2.00
        mock_modifier.is_active = True
        
        initial_size = len(triggers.change_buffer)
        
        # Test insert
        triggers._on_modifier_insert(None, None, mock_modifier)
        assert len(triggers.change_buffer) == initial_size + 1
        
        # Test update with price change
        mock_modifier._price_adjustment_changed = True
        triggers._on_modifier_update(None, None, mock_modifier)
        assert len(triggers.change_buffer) == initial_size + 2
        assert triggers.change_buffer[-1]['change_type'] == 'price_change'
    
    def test_setup_event_listeners(self, triggers):
        """Test that event listeners are properly set up"""
        with patch('backend.core.menu_versioning_triggers.event') as mock_event:
            triggers.setup_event_listeners()
            
            # Should have called event.listen multiple times for different models and events
            assert mock_event.listen.call_count >= 12  # 4 models × 3 events each


class TestModuleFunctions:
    """Test module-level utility functions"""
    
    @pytest.fixture
    def mock_db(self):
        return Mock()
    
    def test_create_manual_version_on_bulk_change_threshold_met(self, mock_db):
        """Test manual version creation when threshold is met"""
        with patch('backend.core.menu_versioning_triggers.menu_versioning_triggers') as mock_triggers:
            mock_triggers.should_create_auto_version.return_value = True
            mock_triggers.create_auto_version.return_value = 456
            
            result = create_manual_version_on_bulk_change(
                mock_db, 
                "bulk_update", 
                affected_count=10, 
                user_id=1
            )
            
            assert result == 456
            mock_triggers.should_create_auto_version.assert_called_once()
            mock_triggers.create_auto_version.assert_called_once()
    
    def test_create_manual_version_on_bulk_change_threshold_not_met(self, mock_db):
        """Test manual version creation when threshold is not met"""
        with patch('backend.core.menu_versioning_triggers.menu_versioning_triggers') as mock_triggers:
            mock_triggers.should_create_auto_version.return_value = False
            
            result = create_manual_version_on_bulk_change(
                mock_db,
                "bulk_update",
                affected_count=2,
                user_id=1
            )
            
            assert result is None
            mock_triggers.create_auto_version.assert_not_called()
    
    def test_disable_enable_auto_versioning(self):
        """Test disabling and enabling auto-versioning"""
        with patch('backend.core.menu_versioning_triggers.menu_versioning_triggers') as mock_triggers:
            disable_auto_versioning()
            assert mock_triggers.enabled is False
            
            enable_auto_versioning()
            assert mock_triggers.enabled is True
    
    def test_get_change_buffer_status(self):
        """Test getting change buffer status"""
        with patch('backend.core.menu_versioning_triggers.menu_versioning_triggers') as mock_triggers:
            mock_triggers.change_buffer = [{'test': 'data'}, {'test': 'data2'}]
            mock_triggers.auto_version_threshold = 10
            mock_triggers.enabled = True
            
            status = get_change_buffer_status()
            
            assert status['buffer_size'] == 2
            assert status['threshold'] == 10
            assert status['enabled'] is True
            assert len(status['recent_changes']) == 2


class TestIntegrationScenarios:
    """Integration test scenarios"""
    
    def test_price_change_cascade(self):
        """Test that price changes properly cascade through the system"""
        triggers = MenuVersioningTriggers()
        
        # Simulate multiple price changes
        items = [Mock(id=i, name=f"Item {i}", price=10.99 + i) for i in range(5)]
        
        for item in items:
            item._price_changed = True
            triggers._on_item_update(None, None, item)
        
        # All should be price_change type
        price_changes = [c for c in triggers.change_buffer if c['change_type'] == 'price_change']
        assert len(price_changes) == 5
    
    def test_mixed_operations_buffer_management(self):
        """Test buffer management with mixed operations"""
        triggers = MenuVersioningTriggers()
        
        # Simulate mixed operations
        operations = [
            ('category', 'create'),
            ('menu_item', 'update'),
            ('menu_item', 'price_change'),
            ('modifier', 'create'),
            ('menu_item', 'delete')
        ]
        
        for entity_type, change_type in operations:
            triggers.add_change_to_buffer({
                'entity_type': entity_type,
                'change_type': change_type,
                'entity_id': len(triggers.change_buffer) + 1
            })
        
        summary = triggers._summarize_changes()
        assert 'create' in summary
        assert 'update' in summary
        assert 'price_change' in summary
        assert 'delete' in summary
    
    def test_performance_large_buffer(self):
        """Test performance with large change buffer"""
        triggers = MenuVersioningTriggers()
        
        # Add many changes quickly
        import time
        start_time = time.time()
        
        for i in range(1000):
            triggers.add_change_to_buffer({
                'entity_id': i,
                'change_type': 'update',
                'entity_type': 'menu_item'
            })
        
        end_time = time.time()
        
        # Should complete quickly (< 1 second) and maintain size limit
        assert end_time - start_time < 1.0
        assert len(triggers.change_buffer) <= 50  # Size limit enforced