# backend/modules/pos_migration/tests/test_data_transformation.py

"""
Test suite for data transformation service.
"""

import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

from ..services import DataTransformationService
from ..schemas.migration_schemas import (
    MigrationPlan,
    FieldMapping,
    FieldTransformationType,
)


@pytest.fixture
def db_session():
    """Mock database session"""
    session = MagicMock(spec=Session)
    return session


@pytest.fixture
def transformation_service(db_session):
    """Create transformation service instance"""
    return DataTransformationService(db_session)


@pytest.fixture
def sample_mappings():
    """Sample field mappings"""
    return [
        FieldMapping(
            source_field="name",
            target_field="name",
            confidence=0.95,
            transformation=FieldTransformationType.NONE
        ),
        FieldMapping(
            source_field="price",
            target_field="price",
            confidence=0.9,
            transformation=FieldTransformationType.PARSE_DECIMAL
        ),
        FieldMapping(
            source_field="description",
            target_field="description",
            confidence=0.85,
            transformation=FieldTransformationType.NONE
        ),
        FieldMapping(
            source_field="category",
            target_field="category_name",
            confidence=0.8,
            transformation=FieldTransformationType.LOWERCASE
        )
    ]


class TestDataTransformationService:
    
    @pytest.mark.asyncio
    async def test_transform_item_basic(self, transformation_service, sample_mappings):
        """Test basic item transformation"""
        
        item = {
            "name": "Cheeseburger",
            "price": "12.99",
            "description": "Delicious beef burger with cheese",
            "category": "MAIN_DISHES"
        }
        
        transformed = await transformation_service._transform_item(
            item, sample_mappings, "menu_item"
        )
        
        assert transformed["name"] == "Cheeseburger"
        assert transformed["price"] == Decimal("12.99")
        assert transformed["description"] == "Delicious beef burger with cheese"
        assert transformed["category_name"] == "main_dishes"
    
    @pytest.mark.asyncio
    async def test_parse_decimal_various_formats(self, transformation_service):
        """Test decimal parsing with various formats"""
        
        # Test integer
        assert transformation_service._parse_decimal(10) == Decimal("10")
        
        # Test float
        assert transformation_service._parse_decimal(12.99) == Decimal("12.99")
        
        # Test string with decimal
        assert transformation_service._parse_decimal("15.50") == Decimal("15.50")
        
        # Test string with currency symbol
        assert transformation_service._parse_decimal("$25.00") == Decimal("25.00")
        
        # Test cents format (e.g., Square uses cents)
        assert transformation_service._parse_decimal("1299") == Decimal("12.99")
        
        # Test with comma
        assert transformation_service._parse_decimal("1,299.00") == Decimal("1299.00")
    
    @pytest.mark.asyncio
    async def test_apply_transformations(self, transformation_service):
        """Test various transformation types"""
        
        # None transformation
        result = await transformation_service._apply_transformation(
            "Test", FieldTransformationType.NONE
        )
        assert result == "Test"
        
        # Lowercase
        result = await transformation_service._apply_transformation(
            "TEST", FieldTransformationType.LOWERCASE
        )
        assert result == "test"
        
        # Uppercase
        result = await transformation_service._apply_transformation(
            "test", FieldTransformationType.UPPERCASE
        )
        assert result == "TEST"
        
        # Parse JSON
        result = await transformation_service._apply_transformation(
            '{"key": "value"}', FieldTransformationType.PARSE_JSON
        )
        assert result == {"key": "value"}
    
    @pytest.mark.asyncio
    async def test_custom_transformations(self, transformation_service):
        """Test custom transformation logic"""
        
        # Split name transformation
        result = await transformation_service._apply_custom_transformation(
            "John Doe", "split_name"
        )
        assert result == {"first_name": "John", "last_name": "Doe"}
        
        # Parse modifiers
        result = await transformation_service._apply_custom_transformation(
            "Extra Cheese: 1.50, Bacon: 2.00", "parse_modifiers"
        )
        assert len(result) == 2
        assert result[0]["name"] == "Extra Cheese"
        assert result[0]["price"] == Decimal("1.50")
        
        # Map POS status
        result = await transformation_service._apply_custom_transformation(
            "enabled", "map_pos_status"
        )
        assert result == "active"
    
    @pytest.mark.asyncio
    async def test_nested_field_access(self, transformation_service):
        """Test accessing nested fields"""
        
        data = {
            "product": {
                "info": {
                    "name": "Test Product",
                    "price": {
                        "amount": 999,
                        "currency": "USD"
                    }
                }
            }
        }
        
        # Test getting nested value
        name = transformation_service._get_nested_value(data, "product.info.name")
        assert name == "Test Product"
        
        price = transformation_service._get_nested_value(data, "product.info.price.amount")
        assert price == 999
        
        # Test non-existent path
        missing = transformation_service._get_nested_value(data, "product.missing.field")
        assert missing is None
    
    @pytest.mark.asyncio
    async def test_set_nested_value(self, transformation_service):
        """Test setting nested values"""
        
        obj = {}
        
        # Set simple value
        transformation_service._set_nested_value(obj, "name", "Test")
        assert obj["name"] == "Test"
        
        # Set nested value
        transformation_service._set_nested_value(obj, "details.price", 100)
        assert obj["details"]["price"] == 100
        
        # Set deeply nested
        transformation_service._set_nested_value(
            obj, "data.product.info.active", True
        )
        assert obj["data"]["product"]["info"]["active"] is True
    
    @pytest.mark.asyncio
    async def test_validate_transformed_data_menu_item(self, transformation_service):
        """Test validation of transformed menu item data"""
        
        # Valid data
        data = {
            "name": "Test Item",
            "price": Decimal("10.99")
        }
        
        validated = transformation_service._validate_transformed_data(
            data, "menu_item"
        )
        
        assert validated["is_active"] is True  # Default added
        assert validated["preparation_time"] == 15  # Default added
        
        # Missing name should raise
        with pytest.raises(Exception) as exc_info:
            transformation_service._validate_transformed_data(
                {"price": 10}, "menu_item"
            )
        assert "name is required" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_validate_field_mappings(self, transformation_service, sample_mappings):
        """Test field mapping validation"""
        
        sample_data = {
            "name": "Test",
            "price": "10.99",
            "description": "Test description"
            # Note: 'category' field is missing
        }
        
        results = await transformation_service.validate_field_mappings(
            sample_mappings, sample_data
        )
        
        # Check results
        assert len(results) == 4
        
        # First three should be valid
        assert results[0]["valid"] is True
        assert results[1]["valid"] is True
        assert results[2]["valid"] is True
        
        # Category mapping should fail (field not found)
        assert results[3]["valid"] is False
        assert "not found" in results[3]["issues"][0]
    
    @pytest.mark.asyncio
    async def test_transform_and_import_batch(self, transformation_service, sample_mappings):
        """Test batch transformation and import"""
        
        data = [
            {
                "name": "Item 1",
                "price": "10.99",
                "description": "First item",
                "category": "FOOD"
            },
            {
                "name": "Item 2",
                "price": "15.50",
                "description": "Second item",
                "category": "BEVERAGE"
            }
        ]
        
        plan = MigrationPlan(
            field_mappings=sample_mappings,
            data_quality_issues=[],
            complexity="simple",
            estimated_hours=1.0,
            risk_factors=[],
            recommendations=[],
            confidence_score=0.9
        )
        
        # Mock the import method
        transformation_service._import_item = AsyncMock(
            side_effect=["id-1", "id-2"]
        )
        
        result = await transformation_service.transform_and_import_batch(
            data=data,
            data_type="menu_item",
            mapping_plan=plan,
            tenant_id="test-tenant"
        )
        
        assert result["success_count"] == 2
        assert result["error_count"] == 0
        assert result["imported_ids"] == ["id-1", "id-2"]
    
    def test_get_mappings_for_type(self, transformation_service, sample_mappings):
        """Test filtering mappings by data type"""
        
        # Add type-specific mappings
        all_mappings = sample_mappings + [
            FieldMapping(
                source_field="customer.email",
                target_field="email",
                confidence=0.9,
                transformation=FieldTransformationType.LOWERCASE
            ),
            FieldMapping(
                source_field="order.total",
                target_field="total_amount",
                confidence=0.95,
                transformation=FieldTransformationType.PARSE_DECIMAL
            )
        ]
        
        # Get menu item mappings
        menu_mappings = transformation_service._get_mappings_for_type(
            all_mappings, "menu_item"
        )
        
        # Should include common fields but not customer/order specific
        assert len(menu_mappings) == 4
        assert all(
            "customer" not in m.source_field and "order" not in m.source_field
            for m in menu_mappings
        )