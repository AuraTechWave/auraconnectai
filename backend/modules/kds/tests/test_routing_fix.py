# backend/modules/kds/tests/test_routing_fix.py

"""
Test for KDS routing fix - ensure no duplicate prefixes
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from ..routes import router as kds_main_router


class TestKDSRouting:
    """Test KDS routing to ensure correct URL paths"""
    
    def test_route_paths_no_duplicate_prefixes(self):
        """Test that routes don't have duplicate /kds prefixes"""
        
        # Create a test FastAPI app
        app = FastAPI()
        app.include_router(kds_main_router)
        
        # Get all routes from the app
        routes = []
        for route in app.routes:
            if hasattr(route, 'path'):
                routes.append(route.path)
        
        # Check that routes don't have duplicate /kds segments
        for route_path in routes:
            # Count occurrences of /kds in the path
            kds_count = route_path.count('/kds')
            
            # Should only appear once in the path
            assert kds_count <= 1, f"Route {route_path} has duplicate /kds prefixes"
            
            # Should not have patterns like /kds/api/v1/kds
            assert '/kds/api/v1/kds' not in route_path, f"Route {route_path} has duplicate /kds prefixes"
    
    def test_correct_endpoint_paths(self):
        """Test that endpoints have correct expected paths"""
        
        # Create a test FastAPI app
        app = FastAPI()
        app.include_router(kds_main_router)
        
        # Expected route patterns (should exist)
        expected_patterns = [
            '/api/v1/kds/stations',
            '/api/v1/kds/performance/real-time',
            '/api/v1/kds/realtime/orders/',
            '/api/v1/kds/performance/station/',
        ]
        
        # Get all routes from the app
        actual_routes = []
        for route in app.routes:
            if hasattr(route, 'path'):
                actual_routes.append(route.path)
        
        # Check that expected patterns exist in some form
        for pattern in expected_patterns:
            # Check if any route contains this pattern (allowing for path parameters)
            pattern_found = any(
                pattern.rstrip('/') in route.rstrip('/') or 
                pattern.replace('/', '') in route.replace('/', '')
                for route in actual_routes
            )
            assert pattern_found, f"Expected route pattern {pattern} not found in {actual_routes}"
    
    def test_no_malformed_routes(self):
        """Test that there are no malformed routes with extra segments"""
        
        # Create a test FastAPI app
        app = FastAPI()
        app.include_router(kds_main_router)
        
        # Get all routes from the app
        malformed_routes = []
        for route in app.routes:
            if hasattr(route, 'path'):
                path = route.path
                
                # Check for malformed patterns
                if '/kds/api/v1/kds' in path:
                    malformed_routes.append(path)
                elif path.count('/api/v1/kds') > 1:
                    malformed_routes.append(path)
                elif '/kds/kds' in path:
                    malformed_routes.append(path)
        
        assert len(malformed_routes) == 0, f"Found malformed routes: {malformed_routes}"


class TestKDSEndpointAccess:
    """Test that KDS endpoints are accessible with correct paths"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        app = FastAPI()
        app.include_router(kds_main_router)
        return TestClient(app)
    
    def test_stations_endpoint_accessible(self, client):
        """Test that stations endpoint is accessible at correct path"""
        
        with patch('backend.modules.kds.routes.kds_routes.get_db'):
            with patch('backend.modules.kds.routes.kds_routes.get_current_user'):
                with patch('backend.modules.kds.routes.kds_routes.KDSService') as mock_service:
                    mock_service.return_value.get_all_stations.return_value = []
                    
                    # This should work (correct path)
                    response = client.get("/api/v1/kds/stations")
                    # Should not be 404 (would indicate wrong path)
                    assert response.status_code != 404
                    
                    # This should NOT work (would be the incorrect duplicate path)
                    response_bad = client.get("/kds/api/v1/kds/stations")
                    assert response_bad.status_code == 404
    
    def test_performance_endpoint_accessible(self, client):
        """Test that performance endpoints are accessible at correct path"""
        
        with patch('backend.modules.kds.routes.kds_performance_routes.get_db'):
            with patch('backend.modules.kds.routes.kds_performance_routes.get_current_user'):
                with patch('backend.modules.kds.routes.kds_performance_routes.KDSPerformanceService') as mock_service:
                    mock_service.return_value.get_real_time_metrics.return_value = {}
                    
                    # This should work (correct path)
                    response = client.get("/api/v1/kds/performance/real-time")
                    assert response.status_code != 404
                    
                    # This should NOT work (duplicate prefix)
                    response_bad = client.get("/kds/api/v1/kds/performance/real-time")
                    assert response_bad.status_code == 404
    
    def test_realtime_endpoint_accessible(self, client):
        """Test that realtime endpoints are accessible at correct path"""
        
        with patch('backend.modules.kds.routes.kds_realtime_routes.get_db'):
            with patch('backend.modules.kds.routes.kds_realtime_routes.get_current_user'):
                with patch('backend.modules.kds.routes.kds_realtime_routes.KDSRealtimeService') as mock_service:
                    mock_service.return_value.get_station_display_items.return_value = []
                    mock_service.return_value.get_station_summary.return_value = {}
                    
                    # This should work (correct path)
                    response = client.get("/api/v1/kds/realtime/station/1/display")
                    assert response.status_code != 404
                    
                    # This should NOT work (duplicate prefix)
                    response_bad = client.get("/kds/api/v1/kds/realtime/station/1/display")
                    assert response_bad.status_code == 404


class TestRouteDiscovery:
    """Test route discovery and documentation"""
    
    def test_openapi_schema_generation(self):
        """Test that OpenAPI schema can be generated without errors"""
        
        # Create a test FastAPI app
        app = FastAPI()
        app.include_router(kds_main_router)
        
        # This should not raise an exception
        try:
            schema = app.openapi()
            assert schema is not None
            assert "paths" in schema
            
            # Check that paths don't have malformed URLs
            for path in schema["paths"].keys():
                assert not path.count("/kds/api/v1/kds"), f"Malformed path in OpenAPI: {path}"
                
        except Exception as e:
            pytest.fail(f"OpenAPI schema generation failed: {e}")
    
    def test_route_tags_preserved(self):
        """Test that route tags are preserved correctly"""
        
        # Create a test FastAPI app
        app = FastAPI()
        app.include_router(kds_main_router)
        
        # Generate OpenAPI schema
        schema = app.openapi()
        
        # Check that KDS-related tags exist
        expected_tags = ["Kitchen Display System", "KDS Performance", "KDS Real-time"]
        
        found_tags = set()
        for path_info in schema["paths"].values():
            for method_info in path_info.values():
                if "tags" in method_info:
                    found_tags.update(method_info["tags"])
        
        for tag in expected_tags:
            assert tag in found_tags, f"Expected tag '{tag}' not found in OpenAPI schema"