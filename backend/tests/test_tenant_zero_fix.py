"""Test to verify tenant ID zero is handled correctly"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import Mock
from core.tenant_context import TenantContext, apply_tenant_filter, validate_tenant_access


def test_tenant_id_zero_is_valid():
    """Test that tenant ID 0 is treated as a valid tenant ID"""
    
    # Clear any existing context
    TenantContext.clear()
    
    # Set context with tenant ID 0
    context = TenantContext.set(restaurant_id=0, location_id=0, user_id=0)
    
    assert context['restaurant_id'] == 0
    assert context['location_id'] == 0
    assert context['user_id'] == 0
    
    # Verify that require_context doesn't reject ID 0
    context = TenantContext.require_context()
    assert context['restaurant_id'] == 0
    assert context['location_id'] == 0
    
    print("✓ Tenant ID 0 is correctly handled in context")


def test_apply_filter_with_tenant_zero():
    """Test that tenant filtering works with tenant ID 0"""
    
    # Set context with tenant ID 0
    TenantContext.set(restaurant_id=0)
    
    # Mock query
    mock_query = Mock()
    mock_filter = Mock()
    mock_query.filter.return_value = mock_filter
    
    # Mock model with restaurant_id field
    class Order:
        __name__ = 'Order'
        restaurant_id = 0
    
    # Apply filter
    result = apply_tenant_filter(mock_query, Order)
    
    # Verify filter was applied (not skipped due to ID being 0)
    mock_query.filter.assert_called_once()
    
    print("✓ Tenant filtering correctly applied for tenant ID 0")


def test_validate_access_with_tenant_zero():
    """Test that validation works correctly with tenant ID 0"""
    
    # Set context with tenant ID 0
    TenantContext.set(restaurant_id=0)
    
    # Entity with matching tenant ID 0
    entity_valid = Mock()
    entity_valid.restaurant_id = 0
    entity_valid.id = 123
    entity_valid.__class__.__name__ = 'TestEntity'
    
    # Should pass validation
    assert validate_tenant_access(entity_valid, raise_on_violation=False) is True
    
    # Entity with different tenant ID
    entity_invalid = Mock()
    entity_invalid.restaurant_id = 1  # Different from context (0)
    entity_invalid.id = 456
    entity_invalid.__class__.__name__ = 'TestEntity'
    
    # Should fail validation
    assert validate_tenant_access(entity_invalid, raise_on_violation=False) is False
    
    print("✓ Tenant validation correctly handles tenant ID 0")


def test_none_vs_zero_distinction():
    """Test that None and 0 are properly distinguished"""
    
    # Clear context
    TenantContext.clear()
    
    # Set context with restaurant_id=0 and location_id=None
    TenantContext.set(restaurant_id=0, location_id=None)
    context = TenantContext.get()
    
    # 0 should be present, None should be None
    assert context['restaurant_id'] == 0
    assert context['location_id'] is None
    
    # require_context should accept this (has restaurant_id=0)
    TenantContext.require_context()  # Should not raise
    
    print("✓ None and 0 are correctly distinguished")


if __name__ == '__main__':
    test_tenant_id_zero_is_valid()
    test_apply_filter_with_tenant_zero()
    test_validate_access_with_tenant_zero()
    test_none_vs_zero_distinction()
    print("\n✅ All tenant ID zero tests passed!")