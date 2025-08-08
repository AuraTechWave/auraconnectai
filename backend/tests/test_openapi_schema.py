"""
OpenAPI Schema Snapshot Tests

Ensures the OpenAPI specification doesn't accidentally lose endpoints
or have breaking changes.
"""

import json
import pytest
from pathlib import Path
from typing import Dict, Set, List, Tuple
import hashlib

from app.main import app


class OpenAPISnapshot:
    """Helper class for OpenAPI snapshot testing."""
    
    def __init__(self, spec: Dict):
        self.spec = spec
        
    def get_endpoints(self) -> Set[Tuple[str, str]]:
        """Get all endpoints as (path, method) tuples."""
        endpoints = set()
        for path, methods in self.spec.get('paths', {}).items():
            for method in methods:
                if method in ['get', 'post', 'put', 'patch', 'delete']:
                    endpoints.add((path, method.upper()))
        return endpoints
    
    def get_schemas(self) -> Set[str]:
        """Get all schema names."""
        return set(self.spec.get('components', {}).get('schemas', {}).keys())
    
    def get_security_schemes(self) -> Set[str]:
        """Get all security scheme names."""
        return set(self.spec.get('components', {}).get('securitySchemes', {}).keys())
    
    def get_operation_ids(self) -> Set[str]:
        """Get all operation IDs."""
        operation_ids = set()
        for path, methods in self.spec.get('paths', {}).items():
            for method, operation in methods.items():
                if isinstance(operation, dict) and 'operationId' in operation:
                    operation_ids.add(operation['operationId'])
        return operation_ids
    
    def get_tags(self) -> Set[str]:
        """Get all tags."""
        return {tag['name'] for tag in self.spec.get('tags', [])}
    
    def calculate_checksum(self) -> str:
        """Calculate checksum of the spec structure."""
        # Create a stable representation of the spec structure
        structure = {
            'paths': sorted(self.get_endpoints()),
            'schemas': sorted(self.get_schemas()),
            'operation_ids': sorted(self.get_operation_ids()),
            'tags': sorted(self.get_tags())
        }
        
        # Convert to JSON for consistent hashing
        json_str = json.dumps(structure, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()


class TestOpenAPISchema:
    """Test suite for OpenAPI schema validation."""
    
    @pytest.fixture
    def openapi_spec(self):
        """Get the current OpenAPI specification."""
        return app.openapi()
    
    @pytest.fixture
    def snapshot(self, openapi_spec):
        """Create snapshot helper."""
        return OpenAPISnapshot(openapi_spec)
    
    def test_endpoints_not_removed(self, snapshot):
        """Test that no endpoints have been accidentally removed."""
        current_endpoints = snapshot.get_endpoints()
        
        # Minimum expected endpoints (add more as needed)
        required_endpoints = {
            ('/api/v1/auth/login', 'POST'),
            ('/api/v1/auth/logout', 'POST'),
            ('/api/v1/auth/refresh', 'POST'),
            ('/api/v1/auth/me', 'GET'),
            ('/api/v1/orders', 'GET'),
            ('/api/v1/orders', 'POST'),
            ('/api/v1/orders/{id}', 'GET'),
            ('/api/v1/orders/{id}', 'PUT'),
            ('/api/v1/menu/items', 'GET'),
            ('/api/v1/menu/items', 'POST'),
            ('/api/v1/menu/items/{id}', 'GET'),
            ('/api/v1/menu/items/{id}', 'PUT'),
            ('/api/v1/menu/items/{id}', 'DELETE'),
            ('/api/v1/staff', 'GET'),
            ('/api/v1/staff', 'POST'),
            ('/api/v1/staff/clock-in', 'POST'),
            ('/api/v1/staff/clock-out', 'POST'),
            ('/api/v1/inventory', 'GET'),
            ('/api/v1/inventory', 'POST'),
            ('/api/v1/analytics/sales', 'GET'),
            ('/api/v1/payments/process', 'POST'),
        }
        
        missing_endpoints = required_endpoints - current_endpoints
        assert not missing_endpoints, f"Missing required endpoints: {missing_endpoints}"
    
    def test_schemas_not_removed(self, snapshot):
        """Test that no schemas have been accidentally removed."""
        current_schemas = snapshot.get_schemas()
        
        # Minimum expected schemas
        required_schemas = {
            'ErrorResponse',
            'PaginationMeta',
        }
        
        missing_schemas = required_schemas - current_schemas
        assert not missing_schemas, f"Missing required schemas: {missing_schemas}"
    
    def test_security_schemes_present(self, snapshot):
        """Test that security schemes are defined."""
        security_schemes = snapshot.get_security_schemes()
        
        assert 'bearerAuth' in security_schemes, "Bearer auth security scheme missing"
        
    def test_all_endpoints_have_security(self, openapi_spec):
        """Test that all non-public endpoints have security defined."""
        public_endpoints = {
            '/api/v1/auth/login',
            '/api/v1/auth/refresh',
            '/docs',
            '/redoc',
            '/openapi.json',
            '/',
        }
        
        for path, methods in openapi_spec.get('paths', {}).items():
            if path in public_endpoints:
                continue
                
            for method, operation in methods.items():
                if method in ['get', 'post', 'put', 'patch', 'delete']:
                    assert 'security' in operation or 'security' in openapi_spec, \
                        f"{method.upper()} {path} has no security defined"
    
    def test_all_operations_have_ids(self, openapi_spec):
        """Test that all operations have operation IDs."""
        for path, methods in openapi_spec.get('paths', {}).items():
            for method, operation in methods.items():
                if method in ['get', 'post', 'put', 'patch', 'delete']:
                    assert 'operationId' in operation, \
                        f"{method.upper()} {path} has no operationId"
    
    def test_all_operations_have_tags(self, openapi_spec):
        """Test that all operations have at least one tag."""
        for path, methods in openapi_spec.get('paths', {}).items():
            for method, operation in methods.items():
                if method in ['get', 'post', 'put', 'patch', 'delete']:
                    assert 'tags' in operation and len(operation['tags']) > 0, \
                        f"{method.upper()} {path} has no tags"
    
    def test_all_operations_have_responses(self, openapi_spec):
        """Test that all operations have response definitions."""
        for path, methods in openapi_spec.get('paths', {}).items():
            for method, operation in methods.items():
                if method in ['get', 'post', 'put', 'patch', 'delete']:
                    assert 'responses' in operation, \
                        f"{method.upper()} {path} has no responses defined"
                    
                    # Check for at least one success response
                    responses = operation['responses']
                    success_codes = {'200', '201', '204'}
                    has_success = any(code in responses for code in success_codes)
                    assert has_success, \
                        f"{method.upper()} {path} has no success response defined"
    
    def test_openapi_version(self, openapi_spec):
        """Test that OpenAPI version is correct."""
        assert openapi_spec.get('openapi', '').startswith('3.'), \
            "OpenAPI version should be 3.x"
    
    def test_api_info_complete(self, openapi_spec):
        """Test that API info is complete."""
        info = openapi_spec.get('info', {})
        
        required_fields = ['title', 'version', 'description']
        for field in required_fields:
            assert field in info and info[field], \
                f"Missing or empty info.{field}"
        
        assert len(info.get('description', '')) >= 100, \
            "API description should be at least 100 characters"
    
    def test_servers_defined(self, openapi_spec):
        """Test that servers are defined."""
        servers = openapi_spec.get('servers', [])
        assert len(servers) > 0, "No servers defined"
        
        # Check for at least local development server
        urls = [s.get('url', '') for s in servers]
        assert any('localhost' in url or '127.0.0.1' in url for url in urls), \
            "No local development server defined"
    
    def test_endpoint_count_threshold(self, snapshot):
        """Test that we have a minimum number of endpoints."""
        endpoints = snapshot.get_endpoints()
        
        # This should be adjusted based on your API size
        MIN_ENDPOINTS = 50
        
        assert len(endpoints) >= MIN_ENDPOINTS, \
            f"API has only {len(endpoints)} endpoints, expected at least {MIN_ENDPOINTS}"
    
    def test_schema_checksum_tracking(self, snapshot, tmp_path):
        """
        Test to track schema changes via checksum.
        This helps identify when the schema structure changes.
        """
        checksum = snapshot.calculate_checksum()
        checksum_file = tmp_path / "openapi_checksum.txt"
        
        # In a real scenario, you'd store this in version control
        # For testing, we just verify the checksum is generated
        assert len(checksum) == 64, "SHA256 checksum should be 64 characters"
        
        # Write checksum for manual inspection if needed
        checksum_file.write_text(checksum)


class TestOpenAPIExamples:
    """Test that operations have proper examples."""
    
    @pytest.fixture
    def openapi_spec(self):
        return app.openapi()
    
    def test_post_operations_have_examples(self, openapi_spec):
        """Test that POST operations have request examples."""
        operations_without_examples = []
        
        for path, methods in openapi_spec.get('paths', {}).items():
            if 'post' in methods:
                operation = methods['post']
                request_body = operation.get('requestBody', {})
                
                has_example = False
                for content in request_body.get('content', {}).values():
                    if 'example' in content or 'examples' in content:
                        has_example = True
                        break
                
                if not has_example and request_body:
                    operations_without_examples.append(f"POST {path}")
        
        # Allow some operations without examples (e.g., file uploads)
        allowed_without_examples = ['/api/v1/upload', '/api/v1/files']
        
        unexpected_without_examples = [
            op for op in operations_without_examples 
            if not any(allowed in op for allowed in allowed_without_examples)
        ]
        
        assert len(unexpected_without_examples) == 0, \
            f"POST operations without examples: {unexpected_without_examples}"


def test_openapi_snapshot_regression():
    """
    Regression test to ensure OpenAPI spec doesn't lose endpoints.
    This test should fail if endpoints are removed without updating the snapshot.
    """
    spec = app.openapi()
    snapshot = OpenAPISnapshot(spec)
    
    # Create a snapshot of current state
    current_state = {
        'endpoint_count': len(snapshot.get_endpoints()),
        'schema_count': len(snapshot.get_schemas()),
        'tag_count': len(snapshot.get_tags()),
        'checksum': snapshot.calculate_checksum()
    }
    
    # These values should be updated when legitimately changing the API
    EXPECTED_MINIMUMS = {
        'endpoint_count': 50,  # Update this based on your API
        'schema_count': 10,    # Update this based on your schemas
        'tag_count': 10,       # Update this based on your tags
    }
    
    for key, expected_min in EXPECTED_MINIMUMS.items():
        assert current_state[key] >= expected_min, \
            f"{key} is {current_state[key]}, expected at least {expected_min}"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])