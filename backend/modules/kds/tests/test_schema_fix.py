# backend/modules/kds/tests/test_schema_fix.py

"""
Test to verify schema redefinition bug fix
"""

import pytest
from datetime import datetime
from modules.kds.schemas.kds_schemas import KDSOrderItemResponse, KDSWebSocketMessage
from modules.kds.models.kds_models import DisplayStatus


class TestSchemaFix:
    """Test that schema redefinition issues are resolved"""
    
    def test_kds_order_item_response_has_complete_fields(self):
        """Test that KDSOrderItemResponse has all required fields including related data"""
        
        # Create a sample response
        item_data = {
            "id": 1,
            "order_item_id": 123,
            "station_id": 5,
            "display_name": "Chicken Sandwich",
            "quantity": 2,
            "modifiers": ["No mayo", "Extra lettuce"],
            "special_instructions": "Well done",
            "status": DisplayStatus.PENDING,
            "sequence_number": 1,
            "received_at": datetime.utcnow(),
            "started_at": None,
            "target_time": datetime.utcnow(),
            "completed_at": None,
            "acknowledged_at": None,
            "priority": 50,
            "course_number": 1,
            "fire_time": None,
            "started_by_id": None,
            "completed_by_id": None,
            "recall_count": 0,
            "last_recalled_at": None,
            "recall_reason": None,
            "wait_time_seconds": 120,
            "is_late": False,
            # These fields were missing in the incomplete definition
            "order_id": 456,
            "table_number": 12,
            "server_name": "John Doe",
        }
        
        # This should work without ValidationError
        response = KDSOrderItemResponse(**item_data)
        
        # Verify all critical fields are present
        assert response.id == 1
        assert response.order_item_id == 123
        assert response.display_name == "Chicken Sandwich"
        
        # Verify the previously missing fields are present
        assert response.order_id == 456
        assert response.table_number == 12
        assert response.server_name == "John Doe"
        
        # Verify computed fields work
        assert response.wait_time_seconds == 120
        assert response.is_late == False
    
    def test_kds_websocket_message_has_required_data_field(self):
        """Test that KDSWebSocketMessage has required data field (not optional)"""
        
        # This should work with required data field
        message_data = {
            "type": "new_item",
            "station_id": 5,
            "data": {
                "item": {
                    "id": 1,
                    "display_name": "Test Item",
                    "status": "pending"
                }
            },
            "timestamp": datetime.utcnow()
        }
        
        message = KDSWebSocketMessage(**message_data)
        
        # Verify fields are present
        assert message.type == "new_item"
        assert message.station_id == 5
        assert message.data is not None
        assert "item" in message.data
        assert message.data["item"]["display_name"] == "Test Item"
    
    def test_kds_websocket_message_validates_type(self):
        """Test that KDSWebSocketMessage validates message type"""
        
        # Valid types should work
        valid_types = ["new_item", "update_item", "remove_item", "station_update", "heartbeat"]
        
        for msg_type in valid_types:
            message = KDSWebSocketMessage(
                type=msg_type,
                data={"test": "data"}
            )
            assert message.type == msg_type
    
    def test_no_schema_redefinition_issues(self):
        """Test that there are no import conflicts or redefinition issues"""
        
        # Import should work without issues
        from modules.kds.schemas import KDSOrderItemResponse as ImportedResponse
        from modules.kds.schemas import KDSWebSocketMessage as ImportedMessage
        
        # Should be the same classes (no redefinition)
        assert ImportedResponse is KDSOrderItemResponse
        assert ImportedMessage is KDSWebSocketMessage
        
        # Create instances to verify they work
        response = ImportedResponse(
            id=1,
            order_item_id=1,
            station_id=1,
            display_name="Test",
            quantity=1,
            modifiers=[],
            special_instructions=None,
            status=DisplayStatus.PENDING,
            sequence_number=1,
            received_at=datetime.utcnow(),
            started_at=None,
            target_time=None,
            completed_at=None,
            acknowledged_at=None,
            priority=0,
            course_number=1,
            fire_time=None,
            started_by_id=None,
            completed_by_id=None,
            recall_count=0,
            last_recalled_at=None,
            recall_reason=None,
            wait_time_seconds=0,
            is_late=False,
            order_id=1,
            table_number=1,
            server_name="Test Server"
        )
        
        message = ImportedMessage(
            type="heartbeat",
            data={"status": "ok"}
        )
        
        assert response.order_id == 1
        assert message.type == "heartbeat"
    
    def test_schema_fields_are_accessible(self):
        """Test that all important fields are accessible and not lost"""
        
        # Test the complete KDSOrderItemResponse
        response = KDSOrderItemResponse(
            id=1,
            order_item_id=1,
            station_id=1,
            display_name="Test Item",
            quantity=1,
            modifiers=[],
            status=DisplayStatus.PENDING,
            received_at=datetime.utcnow(),
            priority=0,
            course_number=1,
            recall_count=0,
            wait_time_seconds=0,
            is_late=False,
            # Test the fields that were missing in duplicate definition
            order_id=123,
            table_number=5,
            server_name="Jane Smith"
        )
        
        # All fields should be accessible
        field_names = [
            'id', 'order_item_id', 'station_id', 'display_name', 'quantity',
            'modifiers', 'special_instructions', 'status', 'sequence_number',
            'received_at', 'started_at', 'target_time', 'completed_at',
            'acknowledged_at', 'priority', 'course_number', 'fire_time',
            'started_by_id', 'completed_by_id', 'recall_count',
            'last_recalled_at', 'recall_reason', 'wait_time_seconds',
            'is_late', 'order_id', 'table_number', 'server_name'
        ]
        
        for field_name in field_names:
            assert hasattr(response, field_name), f"Field {field_name} is missing"
        
        # Verify the critical missing fields work
        assert response.order_id == 123
        assert response.table_number == 5
        assert response.server_name == "Jane Smith"