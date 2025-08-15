# API Response Standardization Guide

## Overview

All API endpoints in AuraConnect AI follow a standardized response format to ensure consistency, predictability, and ease of integration for API consumers.

## Standard Response Format

### Success Response

```json
{
  "success": true,
  "data": {
    // Response payload
  },
  "meta": {
    "timestamp": "2025-08-14T12:00:00Z",
    "request_id": "req_abc123",
    "version": "1.0",
    "processing_time_ms": 45.2,
    "pagination": {
      "current_page": 1,
      "per_page": 20,
      "total": 100,
      "total_pages": 5,
      "has_next": true,
      "has_prev": false
    }
  },
  "errors": [],
  "message": "Operation completed successfully"
}
```

### Error Response

```json
{
  "success": false,
  "data": null,
  "meta": {
    "timestamp": "2025-08-14T12:00:00Z",
    "request_id": "req_abc123",
    "version": "1.0"
  },
  "errors": [
    {
      "code": "VALIDATION_ERROR",
      "message": "Email format is invalid",
      "field": "email",
      "context": {
        "expected_format": "user@example.com"
      }
    }
  ],
  "message": "Validation failed"
}
```

## Response Fields

### Top-Level Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| success | boolean | Yes | Indicates if the request was successful |
| data | any | No | The response payload (null for errors) |
| meta | object | Yes | Response metadata |
| errors | array | Yes | List of errors (empty for success) |
| message | string | No | Optional status message |

### Meta Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| timestamp | datetime | Yes | Response timestamp in ISO 8601 format |
| request_id | string | No | Unique request identifier for tracking |
| version | string | Yes | API version |
| processing_time_ms | float | No | Request processing time in milliseconds |
| pagination | object | No | Pagination information for list endpoints |

### Pagination Fields

| Field | Type | Description |
|-------|------|-------------|
| current_page | integer | Current page number (1-indexed) |
| per_page | integer | Number of items per page |
| total | integer | Total number of items |
| total_pages | integer | Total number of pages |
| has_next | boolean | Whether there is a next page |
| has_prev | boolean | Whether there is a previous page |

### Error Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| code | string | Yes | Machine-readable error code |
| message | string | Yes | Human-readable error message |
| field | string | No | Field that caused the error (for validation) |
| context | object | No | Additional error context |

## Pagination Standards

All list endpoints support standardized pagination parameters:

### Query Parameters

| Parameter | Type | Default | Min | Max | Description |
|-----------|------|---------|-----|-----|-------------|
| page | integer | 1 | 1 | - | Page number (1-indexed) |
| per_page | integer | 20 | 1 | 100 | Items per page |

### Example Request

```
GET /api/v2/customers?page=2&per_page=25
```

### Example Response

```json
{
  "success": true,
  "data": [
    // Array of 25 customer objects
  ],
  "meta": {
    "pagination": {
      "current_page": 2,
      "per_page": 25,
      "total": 150,
      "total_pages": 6,
      "has_next": true,
      "has_prev": true
    }
  }
}
```

## Error Codes

### Standard Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| BAD_REQUEST | 400 | Invalid request parameters |
| UNAUTHORIZED | 401 | Authentication required |
| FORBIDDEN | 403 | Insufficient permissions |
| NOT_FOUND | 404 | Resource not found |
| METHOD_NOT_ALLOWED | 405 | HTTP method not allowed |
| CONFLICT | 409 | Resource conflict (e.g., duplicate) |
| VALIDATION_ERROR | 422 | Validation failed |
| TOO_MANY_REQUESTS | 429 | Rate limit exceeded |
| INTERNAL_ERROR | 500 | Internal server error |
| SERVICE_UNAVAILABLE | 503 | Service temporarily unavailable |

### Domain-Specific Error Codes

| Code | Description |
|------|-------------|
| DUPLICATE_EMAIL | Email already exists |
| INVALID_CREDENTIALS | Invalid login credentials |
| TOKEN_EXPIRED | Authentication token expired |
| INSUFFICIENT_INVENTORY | Not enough inventory |
| PAYMENT_FAILED | Payment processing failed |
| TENANT_MISMATCH | Cross-tenant access attempt |

## Implementation Guide

### Using Response Models (Python/FastAPI)

```python
from core.response_models import StandardResponse, PaginationMeta
from core.response_utils import PaginationParams, create_paginated_response

@router.get("/customers", response_model=StandardResponse[List[Customer]])
async def list_customers(
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db)
):
    # Query customers
    query = db.query(Customer)
    customers, total = pagination.paginate_query(query)
    
    # Return standardized response
    return create_paginated_response(
        items=customers,
        pagination_params=pagination,
        total=total,
        message="Customers retrieved successfully"
    )
```

### Using Response Wrapper Decorator

```python
from core.response_utils import response_wrapper

@router.get("/customer/{id}")
@response_wrapper
async def get_customer(id: int, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer  # Automatically wrapped in StandardResponse
```

### Handling Errors

```python
from core.response_models import ValidationErrorResponse, NotFoundResponse

@router.post("/customers")
async def create_customer(data: CustomerCreate):
    # Validation error
    if not data.email:
        return ValidationErrorResponse.from_validation_errors({
            "email": ["Email is required"]
        })
    
    # Not found error
    if not location_exists(data.location_id):
        return NotFoundResponse.create("Location", data.location_id)
    
    # Success
    return StandardResponse.success(
        data=created_customer,
        message="Customer created successfully"
    )
```

## Frontend Integration

### TypeScript Interfaces

```typescript
interface StandardResponse<T = any> {
  success: boolean;
  data?: T;
  meta: ResponseMeta;
  errors: ErrorDetail[];
  message?: string;
}

interface ResponseMeta {
  timestamp: string;
  request_id?: string;
  version: string;
  processing_time_ms?: number;
  pagination?: PaginationMeta;
}

interface PaginationMeta {
  current_page: number;
  per_page: number;
  total: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
}

interface ErrorDetail {
  code: string;
  message: string;
  field?: string;
  context?: Record<string, any>;
}
```

### API Client Example

```typescript
class ApiClient {
  async get<T>(url: string): Promise<StandardResponse<T>> {
    const response = await fetch(url);
    const data = await response.json();
    
    if (!data.success) {
      throw new ApiError(data.errors, data.message);
    }
    
    return data;
  }
  
  async getPaginated<T>(
    url: string,
    page: number = 1,
    perPage: number = 20
  ): Promise<StandardResponse<T[]>> {
    const params = new URLSearchParams({
      page: page.toString(),
      per_page: perPage.toString()
    });
    
    return this.get<T[]>(`${url}?${params}`);
  }
}
```

## Migration Guide

### Converting Existing Endpoints

1. **Import Required Modules**
   ```python
   from core.response_models import StandardResponse
   from core.response_utils import PaginationParams, create_response
   ```

2. **Update Response Model**
   ```python
   # Before
   @router.get("/items", response_model=List[Item])
   
   # After
   @router.get("/items", response_model=StandardResponse[List[Item]])
   ```

3. **Wrap Response Data**
   ```python
   # Before
   return items
   
   # After
   return StandardResponse.success(data=items)
   ```

4. **Standardize Pagination**
   ```python
   # Before
   def get_items(skip: int = 0, limit: int = 10):
       return db.query(Item).offset(skip).limit(limit).all()
   
   # After
   def get_items(pagination: PaginationParams = Depends()):
       items, total = pagination.paginate_query(db.query(Item))
       return create_paginated_response(items, pagination, total)
   ```

5. **Standardize Errors**
   ```python
   # Before
   raise HTTPException(status_code=404, detail="Not found")
   
   # After
   return NotFoundResponse.create("Item", item_id)
   ```

## Best Practices

1. **Always use StandardResponse** for all API endpoints
2. **Include meaningful error codes** that clients can programmatically handle
3. **Provide pagination** for all list endpoints
4. **Include request IDs** for tracking and debugging
5. **Use appropriate HTTP status codes** alongside error responses
6. **Keep error messages user-friendly** while error codes remain technical
7. **Document all custom error codes** used by your endpoints
8. **Version your API** and include version in meta
9. **Measure and include processing time** for performance monitoring
10. **Validate pagination parameters** to prevent abuse

## Testing

### Example Test Cases

```python
def test_successful_response():
    response = client.get("/api/v2/customers/1")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "data" in data
    assert data["errors"] == []

def test_error_response():
    response = client.get("/api/v2/customers/999")
    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False
    assert data["data"] is None
    assert len(data["errors"]) > 0
    assert data["errors"][0]["code"] == "NOT_FOUND"

def test_pagination():
    response = client.get("/api/v2/customers?page=2&per_page=10")
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["pagination"]["current_page"] == 2
    assert data["meta"]["pagination"]["per_page"] == 10
```

## Monitoring and Analytics

The standardized response format enables better monitoring:

1. **Track success rates** by monitoring `success` field
2. **Measure API performance** using `processing_time_ms`
3. **Debug issues** using `request_id` for tracing
4. **Analyze error patterns** using standardized `error.code`
5. **Monitor pagination usage** to optimize database queries

## Backward Compatibility

During migration, both old and new endpoints can coexist:

- Old endpoints: `/api/customers`
- New endpoints: `/api/v2/customers`

Use API versioning to maintain backward compatibility while migrating clients to the new format.