"""Test to verify redundant tenant filtering is fixed"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import Mock, patch, call
from core.tenant_context import TenantContext, apply_tenant_filter


def test_no_redundant_filtering_in_sales_metrics():
    """Test that tenant filtering is only applied once in sales metrics calculation"""
    
    # Set tenant context
    TenantContext.set(restaurant_id=1)
    
    # Track calls to apply_tenant_filter
    filter_calls = []
    original_apply = apply_tenant_filter
    
    def track_apply_filter(query, model):
        filter_calls.append(model.__name__ if hasattr(model, '__name__') else str(model))
        return original_apply(query, model)
    
    with patch('modules.analytics.services.sales_report_service.apply_tenant_filter', side_effect=track_apply_filter):
        from modules.analytics.services.sales_report_service import SalesReportService
        from modules.analytics.schemas.analytics_schemas import SalesFilterRequest
        
        # Mock database
        db = Mock()
        mock_query = Mock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.with_entities.return_value = mock_query
        mock_query.first.return_value = Mock(
            total_orders=10,
            total_revenue=1000,
            total_items_sold=50,
            average_order_value=100,
            total_discounts=50,
            total_tax=80,
            unique_customers=5
        )
        db.query.return_value = mock_query
        
        service = SalesReportService(db)
        filters = SalesFilterRequest()
        
        # Clear the filter calls list
        filter_calls.clear()
        
        # Call _calculate_sales_metrics
        result = service._calculate_sales_metrics(filters)
        
        # Check that apply_tenant_filter was called only once for Order
        order_filter_count = filter_calls.count('Order')
        print(f"apply_tenant_filter called {order_filter_count} time(s) for Order model")
        
        if order_filter_count == 1:
            print("✓ No redundant filtering in _calculate_sales_metrics")
        else:
            print(f"✗ Redundant filtering detected: {order_filter_count} calls")
            return False
    
    return True


def test_no_redundant_filtering_in_total_revenue():
    """Test that tenant filtering is only applied once in _get_total_revenue"""
    
    # Set tenant context
    TenantContext.set(restaurant_id=1)
    
    filter_calls = []
    original_apply = apply_tenant_filter
    
    def track_apply_filter(query, model):
        filter_calls.append(model.__name__ if hasattr(model, '__name__') else str(model))
        return original_apply(query, model)
    
    with patch('modules.analytics.services.sales_report_service.apply_tenant_filter', side_effect=track_apply_filter):
        from modules.analytics.services.sales_report_service import SalesReportService
        from modules.analytics.schemas.analytics_schemas import SalesFilterRequest
        
        # Mock database
        db = Mock()
        mock_query = Mock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 5000
        db.query.return_value = mock_query
        
        service = SalesReportService(db)
        filters = SalesFilterRequest()
        
        # Clear the filter calls list
        filter_calls.clear()
        
        # Call _get_total_revenue
        result = service._get_total_revenue(filters)
        
        # Check that apply_tenant_filter was called only once
        order_filter_count = filter_calls.count('Order')
        print(f"apply_tenant_filter called {order_filter_count} time(s) for Order in _get_total_revenue")
        
        if order_filter_count == 1:
            print("✓ No redundant filtering in _get_total_revenue")
        else:
            print(f"✗ Redundant filtering detected: {order_filter_count} calls")
            return False
    
    return True


def test_skip_tenant_filter_parameter():
    """Test that skip_tenant_filter parameter works correctly"""
    
    from modules.analytics.services.sales_report_service import SalesReportService
    from modules.analytics.schemas.analytics_schemas import SalesFilterRequest
    
    # Set tenant context
    TenantContext.set(restaurant_id=1)
    
    # Mock database
    db = Mock()
    mock_query = Mock()
    mock_query.filter.return_value = mock_query
    
    service = SalesReportService(db)
    filters = SalesFilterRequest()
    
    # Test with skip_tenant_filter=False (default)
    with patch('modules.analytics.services.sales_report_service.apply_tenant_filter') as mock_apply:
        mock_apply.return_value = mock_query
        result = service._apply_order_filters(mock_query, filters, skip_tenant_filter=False)
        mock_apply.assert_called_once()
        print("✓ Tenant filter applied when skip_tenant_filter=False")
    
    # Test with skip_tenant_filter=True
    with patch('modules.analytics.services.sales_report_service.apply_tenant_filter') as mock_apply:
        result = service._apply_order_filters(mock_query, filters, skip_tenant_filter=True)
        mock_apply.assert_not_called()
        print("✓ Tenant filter skipped when skip_tenant_filter=True")
    
    return True


if __name__ == '__main__':
    success = True
    
    try:
        success = test_no_redundant_filtering_in_sales_metrics() and success
    except Exception as e:
        print(f"✗ Error in test_no_redundant_filtering_in_sales_metrics: {e}")
        success = False
    
    try:
        success = test_no_redundant_filtering_in_total_revenue() and success
    except Exception as e:
        print(f"✗ Error in test_no_redundant_filtering_in_total_revenue: {e}")
        success = False
    
    try:
        success = test_skip_tenant_filter_parameter() and success
    except Exception as e:
        print(f"✗ Error in test_skip_tenant_filter_parameter: {e}")
        success = False
    
    if success:
        print("\n✅ All redundant filtering tests passed!")
    else:
        print("\n❌ Some tests failed")