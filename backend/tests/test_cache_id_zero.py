"""
Test to verify that cache decorators correctly handle ID 0

This test ensures that tenant_id and user_id values of 0 are treated as valid IDs
and not ignored due to being falsy values.
"""

import pytest
from unittest.mock import patch, MagicMock

from core.cache.decorators import cache, cache_menu, invalidate_cache, generate_cache_key
from core.cache.cache_manager import cache_manager


class TestCacheIdZero:
    """Test cache handling of ID 0"""
    
    def test_generate_cache_key_with_zero_id(self):
        """Test that generate_cache_key handles 0 as a valid ID"""
        def sample_func(tenant_id: int, user_id: int):
            pass
        
        # Test with ID 0
        key = generate_cache_key(sample_func, 0, 0)
        assert "0" in key
        
        # Test with kwargs
        key = generate_cache_key(sample_func, tenant_id=0, user_id=0)
        assert "tenant_id:0" in key
        assert "user_id:0" in key
    
    @patch('core.cache.decorators.cache_manager')
    def test_cache_decorator_with_tenant_id_zero(self, mock_manager):
        """Test that cache decorator handles tenant_id=0 correctly"""
        mock_manager.generate_key.return_value = "test:key"
        mock_manager.get.return_value = {"cached": "data"}
        
        @cache(cache_type="test", tenant_aware=True)
        def get_data(tenant_id: int):
            return {"fresh": "data"}
        
        # Call with tenant_id=0
        result = get_data(tenant_id=0)
        
        # Verify tenant_id=0 was passed to generate_key
        call_args = mock_manager.generate_key.call_args
        assert call_args[1]['tenant_id'] == 0  # Should be 0, not None
    
    @patch('core.cache.decorators.cache_manager')
    def test_cache_decorator_with_user_id_zero(self, mock_manager):
        """Test that cache decorator handles user_id=0 correctly"""
        mock_manager.generate_key.return_value = "test:key"
        mock_manager.get.return_value = {"cached": "data"}
        
        @cache(cache_type="test", user_aware=True)
        def get_user_data(user_id: int):
            return {"user": "data"}
        
        # Call with user_id=0
        result = get_user_data(user_id=0)
        
        # Verify user_id=0 was passed to generate_key
        call_args = mock_manager.generate_key.call_args
        assert call_args[1]['user_id'] == 0  # Should be 0, not None
    
    @patch('core.cache.decorators.cache_manager')
    def test_cache_menu_with_restaurant_id_zero(self, mock_manager):
        """Test that cache_menu decorator handles restaurant_id=0 correctly"""
        mock_manager.generate_key.return_value = "menu:key"
        mock_manager.get.return_value = {"menu": "data"}
        
        @cache_menu()
        def get_menu(restaurant_id: int):
            return {"menu": "items"}
        
        # Call with restaurant_id=0
        result = get_menu(restaurant_id=0)
        
        # Verify restaurant_id=0 was treated as tenant_id=0
        call_args = mock_manager.generate_key.call_args
        assert call_args[1]['tenant_id'] == 0  # Should be 0, not None
    
    @patch('core.cache.decorators.cache_manager')
    def test_invalidate_cache_with_tenant_id_zero(self, mock_manager):
        """Test that invalidate_cache decorator handles tenant_id=0 correctly"""
        @invalidate_cache("menu")
        def update_menu(tenant_id: int, data: dict):
            return {"updated": True}
        
        # Call with tenant_id=0
        result = update_menu(tenant_id=0, data={"name": "New"})
        
        # Verify invalidation was called with correct pattern
        mock_manager.invalidate_pattern.assert_called_once()
        call_args = mock_manager.invalidate_pattern.call_args
        assert call_args[0][0] == "menu"
        assert call_args[0][1] == "*t0*"  # Should include t0, not skip invalidation
    
    @patch('core.cache.decorators.cache_manager')
    def test_cache_with_object_having_zero_id(self, mock_manager):
        """Test cache decorator with object attributes having ID 0"""
        mock_manager.generate_key.return_value = "test:key"
        mock_manager.get.return_value = {"cached": "data"}
        
        # Create mock object with ID 0
        class MockObject:
            def __init__(self):
                self.tenant_id = 0
                self.user_id = 0
                self.restaurant_id = 0
        
        @cache(cache_type="test", tenant_aware=True, user_aware=True)
        def process_object(obj: MockObject):
            return {"processed": "data"}
        
        obj = MockObject()
        result = process_object(obj)
        
        # Verify IDs were extracted correctly
        call_args = mock_manager.generate_key.call_args
        assert call_args[1]['tenant_id'] == 0
        assert call_args[1]['user_id'] == 0
    
    def test_cache_key_differentiation_with_zero(self):
        """Test that ID 0 generates different cache keys than None"""
        def sample_func(tenant_id: int = None):
            pass
        
        # Generate keys with different values
        key_none = generate_cache_key(sample_func, tenant_id=None)
        key_zero = generate_cache_key(sample_func, tenant_id=0)
        key_one = generate_cache_key(sample_func, tenant_id=1)
        
        # All keys should be different
        assert key_none != key_zero
        assert key_zero != key_one
        assert key_none != key_one
        
        # Verify 0 is in the key for tenant_id=0
        assert "tenant_id:0" in key_zero
        assert "tenant_id:0" not in key_none
        assert "tenant_id:0" not in key_one


if __name__ == "__main__":
    pytest.main([__file__, "-v"])