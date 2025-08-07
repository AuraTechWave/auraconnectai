# Recipe Management RBAC Tests

This directory contains comprehensive Role-Based Access Control (RBAC) tests for the recipe management endpoints.

## Test Structure

The RBAC tests have been organized into focused test files for better maintainability:

### 1. `test_recipe_rbac_basic_crud.py`
- Tests basic CRUD operations (Create, Read, Update, Delete)
- Verifies permission enforcement for standard recipe operations
- Tests dry-run operations respect permissions

### 2. `test_recipe_rbac_admin_endpoints.py`
- Tests admin-only endpoints like cost recalculation
- Verifies admin users can access all endpoints
- Tests admin-specific query parameters

### 3. `test_recipe_rbac_manager_endpoints.py`
- Tests manager-level operations (bulk updates, approvals)
- Verifies manager permissions are properly enforced
- Tests batch operation limits and edge cases

### 4. `test_recipe_rbac_public_access.py`
- Tests unauthenticated access scenarios
- Tests invalid/expired tokens
- Verifies public endpoints work without authentication
- Tests various authentication schemes

### 5. `test_recipe_rbac_edge_cases.py`
- Tests partial permissions (e.g., create without read)
- Tests custom roles and permission combinations
- Tests malformed permissions and injection attempts
- Tests permission caching scenarios

### 6. `test_recipe_rbac_integration.py`
- Integration tests for complex permission scenarios
- Tests workflow-based permission checks

## Running the Tests

### Run all RBAC tests:
```bash
pytest modules/menu/tests/test_recipe_rbac*.py -v
```

### Run specific test file:
```bash
pytest modules/menu/tests/test_recipe_rbac_basic_crud.py -v
```

### Run with coverage:
```bash
pytest modules/menu/tests/test_recipe_rbac*.py --cov=modules.menu.routes.recipe_routes --cov-report=term-missing
```

### Use the custom test runner:
```bash
# Basic run
python test_recipe_rbac_runner.py

# With coverage (terminal output)
python test_recipe_rbac_runner.py --coverage

# With HTML coverage report
python test_recipe_rbac_runner.py --coverage --cov-format=html

# With XML coverage report (for CI)
python test_recipe_rbac_runner.py --coverage --cov-format=xml
```

## Permission Matrix

| Endpoint | Admin | Manager | Chef | Waiter | Unauthorized |
|----------|-------|---------|------|--------|--------------|
| GET /recipes/{id} | ✅ | ✅ | ✅ | ✅ | ❌ |
| POST /recipes/ | ✅ | ✅ | ✅ | ❌ | ❌ |
| PUT /recipes/{id} | ✅ | ✅ | ✅ | ❌ | ❌ |
| DELETE /recipes/{id} | ✅ | ✅ | ❌ | ❌ | ❌ |
| POST /recipes/recalculate-costs | ✅ | ❌ | ❌ | ❌ | ❌ |
| PUT /recipes/bulk-update | ✅ | ✅ | ❌ | ❌ | ❌ |
| POST /recipes/bulk-activate | ✅ | ✅ | ❌ | ❌ | ❌ |
| POST /recipes/{id}/approve | ✅ | ✅ | ❌ | ❌ | ❌ |
| GET /recipes/{id}/nutrition/public | ✅ | ✅ | ✅ | ✅ | ✅ |

## Test Coverage

The tests cover:
- ✅ Basic CRUD operations with different permission levels
- ✅ Admin-only operations
- ✅ Manager-level operations
- ✅ Public endpoint access
- ✅ Edge cases (partial permissions, custom roles)
- ✅ Negative tests (malformed tokens, invalid permissions)
- ✅ Authentication schemes and token validation
- ✅ Permission injection attempts
- ✅ Concurrent permission changes

## Adding New Tests

When adding new RBAC tests:
1. Identify which category your test belongs to
2. Add it to the appropriate test file
3. Follow the existing test structure and naming conventions
4. Update this README if adding new test categories
5. Ensure all new endpoints are covered in the permission matrix

## Dependencies

Required packages:
- pytest
- pytest-cov (for coverage reporting)
- fastapi
- sqlalchemy
- unittest.mock (built-in)

Install with:
```bash
pip install pytest pytest-cov
```