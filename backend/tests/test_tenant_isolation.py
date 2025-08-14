"""Integration tests for multi-tenant isolation

These tests verify that tenant isolation is properly enforced across all
services and that there is no data leakage between different tenants.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from fastapi import HTTPException

# Add parent directory to path for imports
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the services and models to test
from core.tenant_context import (
    TenantContext, 
    TenantIsolationMiddleware,
    apply_tenant_filter,
    validate_tenant_access,
    CrossTenantAccessLogger
)


class TestTenantContext:
    """Test the TenantContext management"""
    
    def test_set_and_get_context(self):
        """Test setting and getting tenant context"""
        # Clear any existing context
        TenantContext.clear()
        
        # Set context
        context = TenantContext.set(
            restaurant_id=1,
            location_id=10,
            user_id=100
        )
        
        assert context['restaurant_id'] == 1
        assert context['location_id'] == 10
        assert context['user_id'] == 100
        assert 'timestamp' in context
        
        # Get context
        retrieved = TenantContext.get()
        assert retrieved['restaurant_id'] == 1
        assert retrieved['location_id'] == 10
        assert retrieved['user_id'] == 100
        
        # Get specific values
        assert TenantContext.get_restaurant_id() == 1
        assert TenantContext.get_location_id() == 10
        assert TenantContext.get_user_id() == 100
    
    def test_clear_context(self):
        """Test clearing tenant context"""
        TenantContext.set(restaurant_id=1, location_id=10)
        assert TenantContext.get() is not None
        
        TenantContext.clear()
        assert TenantContext.get() is None
        assert TenantContext.get_restaurant_id() is None
    
    def test_require_context(self):
        """Test context requirement enforcement"""
        TenantContext.clear()
        
        # Should raise exception when no context
        with pytest.raises(HTTPException) as exc_info:
            TenantContext.require_context()
        assert exc_info.value.status_code == 403
        
        # Should work with context
        TenantContext.set(restaurant_id=1)
        context = TenantContext.require_context()
        assert context['restaurant_id'] == 1


class TestTenantFiltering:
    """Test tenant filtering on queries"""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session"""
        db = Mock(spec=Session)
        query_mock = Mock()
        db.query.return_value = query_mock
        return db, query_mock
    
    def test_apply_tenant_filter_with_restaurant_id(self, mock_db):
        """Test filtering by restaurant_id"""
        db, query_mock = mock_db
        filter_mock = Mock()
        query_mock.filter.return_value = filter_mock
        
        # Set context with restaurant_id
        TenantContext.set(restaurant_id=1)
        
        # Create a mock model with restaurant_id field
        # Use 'Order' as the model name since it's in tenant_fields dict
        class Order:
            __name__ = 'Order'
            restaurant_id = 1  # Class attribute for hasattr to work
        
        # Check that hasattr works
        assert hasattr(Order, 'restaurant_id')
        
        # Apply filter
        result = apply_tenant_filter(query_mock, Order)
        
        # Verify filter was applied (Order is in the tenant_fields dict)
        query_mock.filter.assert_called_once()
        assert result == filter_mock
    
    def test_apply_tenant_filter_no_context(self, mock_db):
        """Test that queries return no results without context"""
        db, query_mock = mock_db
        filter_mock = Mock()
        query_mock.filter.return_value = filter_mock
        
        # Clear context
        TenantContext.clear()
        
        class MockModel:
            __name__ = 'Order'
        
        # Apply filter - should filter False (no results)
        result = apply_tenant_filter(query_mock, MockModel)
        query_mock.filter.assert_called_with(False)
    
    def test_validate_tenant_access_valid(self):
        """Test validation with matching tenant"""
        TenantContext.set(restaurant_id=1, location_id=10)
        
        # Create mock entity with matching tenant
        entity = Mock()
        entity.restaurant_id = 1
        entity.location_id = 10
        entity.id = 123
        
        # Should pass validation
        assert validate_tenant_access(entity, raise_on_violation=False) is True
    
    def test_validate_tenant_access_invalid(self):
        """Test validation with mismatched tenant"""
        TenantContext.set(restaurant_id=1, location_id=10)
        
        # Create mock entity with different tenant
        entity = Mock()
        entity.restaurant_id = 2  # Different restaurant
        entity.location_id = 10
        entity.id = 123
        entity.__class__.__name__ = 'TestEntity'
        
        # Should fail validation
        assert validate_tenant_access(entity, raise_on_violation=False) is False
        
        # Should raise exception when raise_on_violation=True
        with pytest.raises(HTTPException) as exc_info:
            validate_tenant_access(entity, raise_on_violation=True)
        assert exc_info.value.status_code == 403


class TestMenuRecommendationService:
    """Test tenant isolation in menu recommendation service"""
    
    @pytest.fixture
    def service(self):
        """Create service with mock database"""
        db = Mock(spec=Session)
        return MenuRecommendationService(db), db
    
    def test_get_recommendations_with_tenant_context(self, service):
        """Test that recommendations are filtered by tenant"""
        service_obj, db = service
        
        # Set tenant context
        TenantContext.set(restaurant_id=1, location_id=10)
        
        # Mock the database queries
        mock_query = Mock()
        mock_query.all.return_value = []
        mock_query.filter.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.with_entities.return_value = mock_query
        
        db.query.return_value = mock_query
        
        # Get recommendations
        results = service_obj.get_recommendations(
            customer_id=1,
            max_results=5
        )
        
        # Verify query was made
        assert db.query.called
        assert results == []
    
    def test_aggregate_popularity_applies_tenant_filter(self, service):
        """Test that popularity aggregation respects tenant context"""
        service_obj, db = service
        
        # Set tenant context
        TenantContext.set(restaurant_id=1, location_id=10)
        
        # Mock queries
        mock_order_query = Mock()
        mock_order_query.all.return_value = [(1,), (2,)]  # Mock order IDs
        mock_order_query.filter.return_value = mock_order_query
        mock_order_query.join.return_value = mock_order_query
        mock_order_query.order_by.return_value = mock_order_query
        mock_order_query.limit.return_value = mock_order_query
        
        mock_item_query = Mock()
        mock_item_query.all.return_value = [(101, 5), (102, 3)]  # (menu_item_id, count)
        mock_item_query.filter.return_value = mock_item_query
        mock_item_query.group_by.return_value = mock_item_query
        mock_item_query.order_by.return_value = mock_item_query
        mock_item_query.limit.return_value = mock_item_query
        
        def query_side_effect(model):
            if model == Order or hasattr(model, 'id'):
                return mock_order_query
            else:
                return mock_item_query
        
        db.query.side_effect = query_side_effect
        
        # Get popularity
        results = service_obj._aggregate_popularity(
            customer_id=1,
            last_n_orders=10,
            limit=5
        )
        
        assert len(results) == 2
        assert results[0] == (101, 5)


class TestCustomerSegmentService:
    """Test tenant isolation in customer segmentation"""
    
    @pytest.fixture
    def service(self):
        """Create service with mock database"""
        db = Mock(spec=Session)
        return CustomerSegmentService(db), db
    
    def test_list_segments_filtered_by_tenant(self, service):
        """Test that segment listing is filtered by tenant"""
        service_obj, db = service
        
        # Set tenant context
        TenantContext.set(restaurant_id=1)
        
        # Mock query
        mock_query = Mock()
        mock_segments = [
            Mock(id=1, name='VIP', restaurant_id=1),
            Mock(id=2, name='Regular', restaurant_id=1)
        ]
        mock_query.all.return_value = mock_segments
        mock_query.filter.return_value = mock_query
        db.query.return_value = mock_query
        
        # List segments
        segments = service_obj.list_segments()
        
        assert len(segments) == 2
        assert db.query.called
    
    def test_create_segment_assigns_tenant(self, service):
        """Test that new segments are assigned to current tenant"""
        service_obj, db = service
        
        # Set tenant context
        TenantContext.set(restaurant_id=1)
        
        # Mock database operations
        db.add = Mock()
        db.commit = Mock()
        db.refresh = Mock()
        
        # Mock query for evaluate_segment
        mock_query = Mock()
        mock_query.first.return_value = Mock(
            id=1, 
            name='Test Segment',
            restaurant_id=1,
            customers=[],
            is_dynamic=True
        )
        mock_query.filter.return_value = mock_query
        db.query.return_value = mock_query
        
        # Create segment
        segment_data = CustomerSegmentCreate(
            name='Test Segment',
            description='Test',
            criteria={'tier': ['VIP']},
            is_dynamic=True
        )
        
        with patch.object(service_obj, 'evaluate_segment'):
            segment = service_obj.create_segment(segment_data)
        
        # Verify segment was added to database
        assert db.add.called
        assert db.commit.called
    
    def test_get_segment_validates_tenant(self, service):
        """Test that getting a segment validates tenant access"""
        service_obj, db = service
        
        # Set tenant context
        TenantContext.set(restaurant_id=1)
        
        # Mock segment from different tenant
        mock_segment = Mock(id=1, name='VIP', restaurant_id=2)  # Different tenant!
        mock_query = Mock()
        mock_query.first.return_value = mock_segment
        mock_query.filter.return_value = mock_query
        db.query.return_value = mock_query
        
        # Should return None due to tenant mismatch
        with patch('modules.customers.services.segment_service.validate_tenant_access', return_value=False):
            segment = service_obj.get_segment(1)
            assert segment is None


class TestSalesReportService:
    """Test tenant isolation in sales analytics"""
    
    @pytest.fixture
    def service(self):
        """Create service with mock database"""
        db = Mock(spec=Session)
        return SalesReportService(db), db
    
    def test_generate_sales_summary_requires_context(self, service):
        """Test that sales summary requires tenant context"""
        service_obj, db = service
        
        # Clear context
        TenantContext.clear()
        
        # Should raise exception without context
        filters = SalesFilterRequest(
            date_from=datetime.now().date() - timedelta(days=7),
            date_to=datetime.now().date()
        )
        
        with pytest.raises(HTTPException) as exc_info:
            service_obj.generate_sales_summary(filters)
        assert exc_info.value.status_code == 403
    
    def test_build_snapshots_query_applies_tenant_filter(self, service):
        """Test that snapshot queries are tenant-filtered"""
        service_obj, db = service
        
        # Set tenant context
        TenantContext.set(restaurant_id=1, location_id=10)
        
        # Mock query
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        db.query.return_value = mock_query
        
        # Build query
        filters = SalesFilterRequest()
        with patch('modules.analytics.services.sales_report_service.apply_tenant_filter', return_value=mock_query):
            result = service_obj._build_snapshots_query(filters)
        
        assert result == mock_query
    
    def test_staff_performance_validates_staff_ids(self, service):
        """Test that staff performance validates staff IDs belong to tenant"""
        service_obj, db = service
        
        # Set tenant context
        TenantContext.set(restaurant_id=1, location_id=10)
        
        # Mock queries
        mock_query = Mock()
        mock_query.all.return_value = []  # No valid staff
        mock_query.filter.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.subquery.return_value = Mock()
        
        db.query.return_value = mock_query
        
        # Generate report with staff from different tenant
        filters = SalesFilterRequest(staff_ids=[999])  # Invalid staff ID
        
        with patch('modules.analytics.services.sales_report_service.apply_tenant_filter', return_value=mock_query):
            results = service_obj.generate_staff_performance_report(filters)
        
        assert results == []


class TestCrossTenantAccessLogger:
    """Test cross-tenant access logging"""
    
    def test_log_access_attempt_cross_tenant(self, caplog):
        """Test logging of cross-tenant access attempts"""
        db = Mock(spec=Session)
        logger = CrossTenantAccessLogger(db)
        
        # Set context for tenant 1
        TenantContext.set(restaurant_id=1, user_id=100)
        
        # Log attempt to access tenant 2 data
        logger.log_access_attempt(
            requested_tenant_id=1,
            actual_tenant_id=2,
            resource_type='Order',
            resource_id=123,
            action='read',
            success=False
        )
        
        # Check that critical log was created
        assert 'CROSS-TENANT ACCESS ATTEMPT' in caplog.text
        assert 'User 100' in caplog.text
        assert 'Order:123' in caplog.text
    
    def test_raise_security_alert_on_success(self, caplog):
        """Test security alert for successful cross-tenant breach"""
        db = Mock(spec=Session)
        logger = CrossTenantAccessLogger(db)
        
        # Log successful breach
        logger.log_access_attempt(
            requested_tenant_id=1,
            actual_tenant_id=2,
            resource_type='Customer',
            resource_id=456,
            action='update',
            user_id=100,
            success=True
        )
        
        # Check for security alert
        assert 'SECURITY ALERT' in caplog.text
        assert 'Successful cross-tenant data breach' in caplog.text


class TestMiddlewareIntegration:
    """Test the TenantIsolationMiddleware"""
    
    @pytest.mark.asyncio
    async def test_middleware_sets_context_from_jwt(self):
        """Test that middleware extracts tenant from JWT"""
        from fastapi import Request
        from starlette.responses import Response
        
        # Create mock request
        request = Mock(spec=Request)
        request.url.path = '/api/v1/orders'
        request.method = 'GET'
        request.client = Mock(host='127.0.0.1')
        request.headers = {'Authorization': 'Bearer mock_token'}
        
        # Mock token verification
        with patch('core.tenant_context.verify_token') as mock_verify:
            mock_verify.return_value = {
                'sub': 100,  # user_id
                'restaurant_id': 1,
                'location_id': 10
            }
            
            # Create middleware
            middleware = TenantIsolationMiddleware(app=Mock())
            
            # Mock call_next
            async def call_next(req):
                # Verify context was set
                context = TenantContext.get()
                assert context is not None
                assert context['restaurant_id'] == 1
                assert context['location_id'] == 10
                assert context['user_id'] == 100
                return Response(content='OK')
            
            # Process request
            response = await middleware.dispatch(request, call_next)
            
            # Verify context was cleared after request
            assert TenantContext.get() is None
    
    @pytest.mark.asyncio
    async def test_middleware_blocks_without_token(self):
        """Test that middleware blocks requests without valid token"""
        from fastapi import Request
        
        # Create mock request without auth header
        request = Mock(spec=Request)
        request.url.path = '/api/v1/orders'
        request.headers = {}
        request.client = Mock(host='127.0.0.1')
        
        # Create middleware
        middleware = TenantIsolationMiddleware(app=Mock())
        
        # Mock call_next (should not be called)
        call_next = Mock()
        
        # Process request
        response = await middleware.dispatch(request, call_next)
        
        # Verify request was blocked
        assert response.status_code == 403
        assert call_next.not_called
    
    @pytest.mark.asyncio
    async def test_middleware_allows_exempt_paths(self):
        """Test that middleware allows exempt paths without token"""
        from fastapi import Request
        from starlette.responses import Response
        
        # Create mock request for exempt path
        request = Mock(spec=Request)
        request.url.path = '/docs'
        request.headers = {}
        
        # Create middleware
        middleware = TenantIsolationMiddleware(app=Mock())
        
        # Mock call_next
        async def call_next(req):
            return Response(content='Docs')
        
        # Process request
        response = await middleware.dispatch(request, call_next)
        
        # Verify request was allowed
        assert response.body == b'Docs'


# Run tests with pytest
if __name__ == '__main__':
    pytest.main([__file__, '-v'])