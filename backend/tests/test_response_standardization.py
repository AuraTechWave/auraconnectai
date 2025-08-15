"""
Tests for API Response Standardization

Tests the standard response format, pagination, and error handling.
"""

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from typing import List, Optional
from pydantic import BaseModel

from core.response_models import (
    StandardResponse,
    PaginationMeta,
    ErrorDetail,
    NotFoundResponse,
    ValidationErrorResponse
)
from core.response_utils import (
    PaginationParams,
    create_response,
    create_paginated_response,
    create_error_response,
    response_wrapper,
    ResponseBuilder
)
from core.response_middleware import ResponseStandardizationMiddleware


# Test models
class TestItem(BaseModel):
    id: int
    name: str
    value: float


# Test app setup
app = FastAPI()
app.add_middleware(ResponseStandardizationMiddleware)


@app.get("/test/success")
async def test_success_endpoint():
    """Test successful response"""
    return {"message": "Success", "data": {"id": 1, "name": "Test"}}


@app.get("/test/error")
async def test_error_endpoint():
    """Test error response"""
    raise HTTPException(status_code=404, detail="Item not found")


@app.get("/test/standard", response_model=StandardResponse[TestItem])
async def test_standard_response():
    """Test endpoint returning StandardResponse"""
    item = TestItem(id=1, name="Test Item", value=99.99)
    return StandardResponse.success(data=item, message="Item retrieved")


@app.get("/test/paginated", response_model=StandardResponse[List[TestItem]])
async def test_paginated_response(page: int = 1, per_page: int = 10):
    """Test paginated response"""
    items = [
        TestItem(id=i, name=f"Item {i}", value=float(i * 10))
        for i in range(1, 101)
    ]
    
    start = (page - 1) * per_page
    end = start + per_page
    page_items = items[start:end]
    
    return StandardResponse.paginated(
        data=page_items,
        page=page,
        per_page=per_page,
        total=len(items)
    )


@app.get("/test/wrapped")
@response_wrapper
async def test_wrapped_endpoint():
    """Test endpoint with response wrapper decorator"""
    return {"id": 1, "status": "active"}


client = TestClient(app)


class TestStandardResponseModels:
    """Test standard response model functionality"""
    
    def test_success_response(self):
        """Test creating a successful response"""
        response = StandardResponse.success(
            data={"id": 1, "name": "Test"},
            message="Success"
        )
        
        assert response.success is True
        assert response.data == {"id": 1, "name": "Test"}
        assert response.message == "Success"
        assert response.errors == []
        assert response.meta.version == "1.0"
    
    def test_error_response(self):
        """Test creating an error response"""
        response = StandardResponse.error(
            message="Something went wrong",
            code="ERROR_CODE"
        )
        
        assert response.success is False
        assert response.data is None
        assert response.message == "Something went wrong"
        assert len(response.errors) == 1
        assert response.errors[0].code == "ERROR_CODE"
        assert response.errors[0].message == "Something went wrong"
    
    def test_paginated_response(self):
        """Test creating a paginated response"""
        items = [{"id": i} for i in range(1, 11)]
        response = StandardResponse.paginated(
            data=items,
            page=2,
            per_page=10,
            total=25
        )
        
        assert response.success is True
        assert response.data == items
        assert response.meta.pagination.current_page == 2
        assert response.meta.pagination.per_page == 10
        assert response.meta.pagination.total == 25
        assert response.meta.pagination.total_pages == 3
        assert response.meta.pagination.has_next is True
        assert response.meta.pagination.has_prev is True
    
    def test_validation_error_response(self):
        """Test validation error response"""
        errors = {
            "email": ["Email is required", "Email format is invalid"],
            "password": ["Password is too short"]
        }
        response = ValidationErrorResponse.from_validation_errors(errors)
        
        assert response.success is False
        assert len(response.errors) == 3
        assert response.message == "Validation failed"
        
        # Check error details
        email_errors = [e for e in response.errors if e.field == "email"]
        assert len(email_errors) == 2
    
    def test_not_found_response(self):
        """Test not found response"""
        response = NotFoundResponse.create("User", 123)
        
        assert response.success is False
        assert response.message == "User with ID 123 not found"
        assert response.errors[0].code == "NOT_FOUND"


class TestPaginationUtils:
    """Test pagination utilities"""
    
    def test_pagination_params(self):
        """Test PaginationParams class"""
        params = PaginationParams(page=3, per_page=20)
        
        assert params.page == 3
        assert params.per_page == 20
        assert params.skip == 40  # (3-1) * 20
        assert params.limit == 20
    
    def test_pagination_meta_creation(self):
        """Test creating pagination metadata"""
        params = PaginationParams(page=2, per_page=10)
        meta = params.create_pagination_meta(total=45)
        
        assert meta.current_page == 2
        assert meta.per_page == 10
        assert meta.total == 45
        assert meta.total_pages == 5
        assert meta.has_next is True
        assert meta.has_prev is True
    
    def test_pagination_edge_cases(self):
        """Test pagination edge cases"""
        # First page
        params = PaginationParams(page=1, per_page=10)
        meta = params.create_pagination_meta(total=25)
        assert meta.has_prev is False
        assert meta.has_next is True
        
        # Last page
        params = PaginationParams(page=3, per_page=10)
        meta = params.create_pagination_meta(total=25)
        assert meta.has_prev is True
        assert meta.has_next is False
        
        # Single page
        params = PaginationParams(page=1, per_page=50)
        meta = params.create_pagination_meta(total=10)
        assert meta.has_prev is False
        assert meta.has_next is False


class TestResponseBuilder:
    """Test ResponseBuilder pattern"""
    
    def test_builder_success(self):
        """Test building a successful response"""
        response = (ResponseBuilder()
            .with_data({"id": 1, "name": "Test"})
            .with_message("Success")
            .with_meta("request_id", "req_123")
            .with_pagination(1, 10, 100)
            .build())
        
        assert response.success is True
        assert response.data == {"id": 1, "name": "Test"}
        assert response.message == "Success"
        assert response.meta.pagination.total == 100
    
    def test_builder_error(self):
        """Test building an error response"""
        response = (ResponseBuilder()
            .with_error("VALIDATION", "Invalid input", "email")
            .with_error("REQUIRED", "Field is required", "password")
            .with_message("Validation failed")
            .build())
        
        assert response.success is False
        assert len(response.errors) == 2
        assert response.message == "Validation failed"


class TestMiddlewareIntegration:
    """Test middleware integration"""
    
    def test_success_endpoint_wrapped(self):
        """Test successful endpoint gets wrapped"""
        response = client.get("/test/success")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["data"] == {"message": "Success", "data": {"id": 1, "name": "Test"}}
        assert "meta" in data
        assert "request_id" in data["meta"]
        assert "processing_time_ms" in data["meta"]
    
    def test_error_endpoint_wrapped(self):
        """Test error endpoint gets wrapped"""
        response = client.get("/test/error")
        assert response.status_code == 404
        
        data = response.json()
        assert data["success"] is False
        assert data["message"] == "Item not found"
        assert len(data["errors"]) > 0
        assert data["errors"][0]["code"] == "NOT_FOUND"
    
    def test_standard_response_passthrough(self):
        """Test StandardResponse passes through with updated meta"""
        response = client.get("/test/standard")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["data"]["name"] == "Test Item"
        assert data["message"] == "Item retrieved"
        assert "request_id" in data["meta"]
        assert "processing_time_ms" in data["meta"]
    
    def test_paginated_response(self):
        """Test paginated response structure"""
        response = client.get("/test/paginated?page=2&per_page=5")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) == 5
        assert data["meta"]["pagination"]["current_page"] == 2
        assert data["meta"]["pagination"]["per_page"] == 5
        assert data["meta"]["pagination"]["total"] == 100
        assert data["meta"]["pagination"]["has_prev"] is True
        assert data["meta"]["pagination"]["has_next"] is True
    
    def test_wrapped_decorator(self):
        """Test response wrapper decorator"""
        response = client.get("/test/wrapped")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["data"] == {"id": 1, "status": "active"}
        assert "request_id" in data["meta"]
        assert "processing_time_ms" in data["meta"]


class TestErrorHandling:
    """Test error handling and standardization"""
    
    def test_validation_error_format(self):
        """Test validation error formatting"""
        errors = {
            "email": ["Invalid format"],
            "age": ["Must be positive"]
        }
        
        from core.response_utils import format_validation_errors
        error_details = format_validation_errors(errors)
        
        assert len(error_details) == 2
        assert all(e.code == "VALIDATION_ERROR" for e in error_details)
        assert any(e.field == "email" for e in error_details)
        assert any(e.field == "age" for e in error_details)
    
    def test_database_error_handling(self):
        """Test database error handling"""
        from core.response_utils import handle_database_error
        
        # Test duplicate key error
        error = Exception("duplicate key value violates unique constraint")
        response = handle_database_error(error, "user creation")
        assert response.status_code == 409
        
        # Test foreign key error
        error = Exception("foreign key constraint fails")
        response = handle_database_error(error, "order creation")
        assert response.status_code == 400
        
        # Test not found error
        error = Exception("record not found")
        response = handle_database_error(error, "user lookup")
        assert response.status_code == 404
        
        # Test generic database error
        error = Exception("database connection failed")
        response = handle_database_error(error, "query execution")
        assert response.status_code == 500


if __name__ == "__main__":
    pytest.main([__file__, "-v"])