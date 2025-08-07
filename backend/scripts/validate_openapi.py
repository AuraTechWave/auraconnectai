#!/usr/bin/env python3

"""
Validate OpenAPI specification for completeness and coverage.
Ensures API documentation quality and prevents regression.
"""

import json
import sys
import os
from pathlib import Path
from typing import Dict, List, Tuple, Set
import re

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.main import app


class OpenAPIValidator:
    """Validator for OpenAPI specification coverage and quality."""
    
    def __init__(self, spec: Dict):
        self.spec = spec
        self.errors = []
        self.warnings = []
        self.info = []
        
    def validate(self) -> bool:
        """Run all validation checks."""
        self._validate_metadata()
        self._validate_paths()
        self._validate_schemas()
        self._validate_security()
        self._validate_examples()
        self._validate_tags()
        self._validate_responses()
        self._calculate_coverage()
        
        # Print results
        self._print_results()
        
        # Return True if no errors
        return len(self.errors) == 0
    
    def _validate_metadata(self):
        """Validate OpenAPI metadata."""
        info = self.spec.get('info', {})
        
        required_fields = ['title', 'version', 'description']
        for field in required_fields:
            if not info.get(field):
                self.errors.append(f"Missing required info field: {field}")
        
        # Check description length
        description = info.get('description', '')
        if len(description) < 100:
            self.warnings.append("API description is too short (< 100 characters)")
        
        # Check for contact info
        if not info.get('contact'):
            self.warnings.append("Missing contact information")
        
        # Check for license
        if not info.get('license'):
            self.warnings.append("Missing license information")
    
    def _validate_paths(self):
        """Validate API paths and operations."""
        paths = self.spec.get('paths', {})
        
        if not paths:
            self.errors.append("No API paths defined")
            return
        
        for path, operations in paths.items():
            # Check path format
            if not path.startswith('/'):
                self.errors.append(f"Path '{path}' must start with '/'")
            
            # Check for at least one operation
            http_methods = {'get', 'post', 'put', 'patch', 'delete', 'options', 'head'}
            path_methods = set(operations.keys()) & http_methods
            
            if not path_methods:
                self.errors.append(f"Path '{path}' has no HTTP operations")
            
            # Validate each operation
            for method in path_methods:
                operation = operations[method]
                self._validate_operation(path, method, operation)
    
    def _validate_operation(self, path: str, method: str, operation: Dict):
        """Validate individual operation."""
        # Check for summary
        if not operation.get('summary'):
            self.warnings.append(f"{method.upper()} {path}: Missing summary")
        
        # Check for description
        if not operation.get('description'):
            self.warnings.append(f"{method.upper()} {path}: Missing description")
        
        # Check for operation ID
        if not operation.get('operationId'):
            self.errors.append(f"{method.upper()} {path}: Missing operationId")
        
        # Check for tags
        if not operation.get('tags'):
            self.warnings.append(f"{method.upper()} {path}: No tags assigned")
        
        # Check for responses
        responses = operation.get('responses', {})
        if not responses:
            self.errors.append(f"{method.upper()} {path}: No responses defined")
        else:
            # Check for success response
            success_codes = {'200', '201', '204'}
            if not any(code in responses for code in success_codes):
                self.warnings.append(f"{method.upper()} {path}: No success response defined")
            
            # Check for error responses
            if '400' not in responses and method.lower() in ['post', 'put', 'patch']:
                self.warnings.append(f"{method.upper()} {path}: Missing 400 Bad Request response")
    
    def _validate_schemas(self):
        """Validate schema definitions."""
        schemas = self.spec.get('components', {}).get('schemas', {})
        
        if not schemas:
            self.warnings.append("No schema definitions found")
            return
        
        for schema_name, schema in schemas.items():
            # Check for description
            if not schema.get('description'):
                self.warnings.append(f"Schema '{schema_name}': Missing description")
            
            # Check for required fields in objects
            if schema.get('type') == 'object':
                properties = schema.get('properties', {})
                required = schema.get('required', [])
                
                if not properties:
                    self.warnings.append(f"Schema '{schema_name}': Object has no properties")
                
                # Check property descriptions
                for prop_name, prop in properties.items():
                    if not prop.get('description'):
                        self.info.append(f"Schema '{schema_name}.{prop_name}': Missing description")
    
    def _validate_security(self):
        """Validate security definitions."""
        security_schemes = self.spec.get('components', {}).get('securitySchemes', {})
        
        if not security_schemes:
            self.errors.append("No security schemes defined")
        
        # Check for JWT/Bearer auth
        has_bearer = any(
            scheme.get('type') == 'http' and scheme.get('scheme') == 'bearer'
            for scheme in security_schemes.values()
        )
        
        if not has_bearer:
            self.warnings.append("No Bearer/JWT authentication scheme defined")
    
    def _validate_examples(self):
        """Validate that operations have examples."""
        paths = self.spec.get('paths', {})
        operations_without_examples = []
        
        for path, operations in paths.items():
            for method, operation in operations.items():
                if method in ['get', 'post', 'put', 'patch']:
                    # Check request body examples
                    request_body = operation.get('requestBody', {})
                    content = request_body.get('content', {})
                    
                    has_example = False
                    for media_type, media in content.items():
                        if 'example' in media or 'examples' in media:
                            has_example = True
                            break
                    
                    if method in ['post', 'put', 'patch'] and not has_example:
                        operations_without_examples.append(f"{method.upper()} {path}")
        
        if operations_without_examples:
            self.info.append(
                f"Operations without request examples: {len(operations_without_examples)}"
            )
    
    def _validate_tags(self):
        """Validate tag definitions and usage."""
        defined_tags = {tag['name'] for tag in self.spec.get('tags', [])}
        used_tags = set()
        
        # Collect all used tags
        for path, operations in self.spec.get('paths', {}).items():
            for method, operation in operations.items():
                if isinstance(operation, dict):
                    used_tags.update(operation.get('tags', []))
        
        # Check for undefined tags
        undefined_tags = used_tags - defined_tags
        if undefined_tags:
            self.warnings.append(f"Undefined tags used: {', '.join(undefined_tags)}")
        
        # Check for unused tags
        unused_tags = defined_tags - used_tags
        if unused_tags:
            self.info.append(f"Defined but unused tags: {', '.join(unused_tags)}")
    
    def _validate_responses(self):
        """Validate response definitions."""
        paths = self.spec.get('paths', {})
        
        for path, operations in paths.items():
            for method, operation in operations.items():
                if isinstance(operation, dict):
                    responses = operation.get('responses', {})
                    
                    for status_code, response in responses.items():
                        # Check for description
                        if not response.get('description'):
                            self.errors.append(
                                f"{method.upper()} {path} - Response {status_code}: Missing description"
                            )
    
    def _calculate_coverage(self):
        """Calculate API documentation coverage metrics."""
        paths = self.spec.get('paths', {})
        total_operations = 0
        documented_operations = 0
        operations_with_examples = 0
        
        for path, operations in paths.items():
            for method, operation in operations.items():
                if method in ['get', 'post', 'put', 'patch', 'delete']:
                    total_operations += 1
                    
                    # Check if well-documented
                    if (operation.get('summary') and 
                        operation.get('description') and 
                        operation.get('responses')):
                        documented_operations += 1
                    
                    # Check for examples
                    if self._has_examples(operation):
                        operations_with_examples += 1
        
        if total_operations > 0:
            coverage = (documented_operations / total_operations) * 100
            example_coverage = (operations_with_examples / total_operations) * 100
            
            self.info.append(f"Documentation coverage: {coverage:.1f}% ({documented_operations}/{total_operations})")
            self.info.append(f"Example coverage: {example_coverage:.1f}% ({operations_with_examples}/{total_operations})")
            
            # Enforce minimum coverage
            min_coverage = 80.0
            if coverage < min_coverage:
                self.errors.append(f"Documentation coverage {coverage:.1f}% is below minimum {min_coverage}%")
    
    def _has_examples(self, operation: Dict) -> bool:
        """Check if operation has examples."""
        # Check request body
        request_body = operation.get('requestBody', {})
        for content in request_body.get('content', {}).values():
            if 'example' in content or 'examples' in content:
                return True
        
        # Check responses
        for response in operation.get('responses', {}).values():
            for content in response.get('content', {}).values():
                if 'example' in content or 'examples' in content:
                    return True
        
        return False
    
    def _print_results(self):
        """Print validation results."""
        print("=" * 70)
        print("OpenAPI Validation Results")
        print("=" * 70)
        
        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"   - {error}")
        
        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"   - {warning}")
        
        if self.info:
            print(f"\nℹ️  INFO ({len(self.info)}):")
            for info in self.info:
                print(f"   - {info}")
        
        if not self.errors:
            print("\n✅ OpenAPI specification passed validation!")
        else:
            print(f"\n❌ OpenAPI specification has {len(self.errors)} errors that must be fixed!")
        
        print("=" * 70)


def validate_endpoint_coverage():
    """Validate that all FastAPI routes are documented."""
    from fastapi.routing import APIRoute
    
    # Get all routes from the app
    api_routes = []
    for route in app.routes:
        if isinstance(route, APIRoute) and not route.path.startswith('/docs') and not route.path.startswith('/redoc'):
            api_routes.append((route.path, list(route.methods)))
    
    # Get documented paths from OpenAPI
    openapi_spec = app.openapi()
    documented_paths = set(openapi_spec.get('paths', {}).keys())
    
    # Convert FastAPI paths to OpenAPI format
    missing_endpoints = []
    for path, methods in api_routes:
        # Convert path parameters from {id} to {id}
        openapi_path = re.sub(r'{(\w+)}', r'{\1}', path)
        
        if openapi_path not in documented_paths:
            missing_endpoints.append(f"{', '.join(methods)} {path}")
    
    if missing_endpoints:
        print(f"\n⚠️  WARNING: {len(missing_endpoints)} endpoints are not documented in OpenAPI:")
        for endpoint in missing_endpoints[:10]:  # Show first 10
            print(f"   - {endpoint}")
        if len(missing_endpoints) > 10:
            print(f"   ... and {len(missing_endpoints) - 10} more")
        return False
    
    return True


def main():
    """Main validation function."""
    # Generate OpenAPI spec
    openapi_spec = app.openapi()
    
    # Create validator
    validator = OpenAPIValidator(openapi_spec)
    
    # Run validation
    is_valid = validator.validate()
    
    # Check endpoint coverage
    coverage_valid = validate_endpoint_coverage()
    
    # Exit with appropriate code
    if is_valid and coverage_valid:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()