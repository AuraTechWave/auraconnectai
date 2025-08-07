# Recipe Management RBAC Tests

This directory contains comprehensive Role-Based Access Control (RBAC) tests for the recipe management endpoints.

## Test Coverage

### 1. **test_recipe_rbac.py**
Unit tests for permission enforcement on individual endpoints:
- Basic CRUD operations (Create, Read, Update, Delete)
- Admin-only endpoints (`/recalculate-costs`)
- Manager-only endpoints (bulk operations, approval)
- Public endpoints (nutrition information)
- Sub-recipe management permissions
- Dry run operations with permission checks

### 2. **test_recipe_rbac_integration.py**
Integration tests for complete permission flow:
- Permission decorator integration
- Service-level permission enforcement
- Role hierarchy and inheritance
- Cascading permissions for related operations
- Data filtering based on user roles

## User Roles and Permissions

| Role | Permissions |
|------|------------|
| **Admin** | `menu:create`, `menu:read`, `menu:update`, `menu:delete`, `admin:recipes`, `manager:recipes` |
| **Manager** | `menu:create`, `menu:read`, `menu:update`, `menu:delete`, `manager:recipes` |
| **Chef** | `menu:create`, `menu:read`, `menu:update` |
| **Waiter** | `menu:read` |
| **Unauthorized** | No recipe permissions |

## Endpoint Permission Matrix

| Endpoint | Required Permission | Admin | Manager | Chef | Waiter |
|----------|-------------------|-------|---------|------|--------|
| `POST /recipes/` | `menu:create` | ✅ | ✅ | ✅ | ❌ |
| `GET /recipes/{id}` | `menu:read` | ✅ | ✅ | ✅ | ✅ |
| `PUT /recipes/{id}` | `menu:update` | ✅ | ✅ | ✅ | ❌ |
| `DELETE /recipes/{id}` | `menu:delete` | ✅ | ✅ | ❌ | ❌ |
| `POST /recipes/recalculate-costs` | `admin:recipes` | ✅ | ❌ | ❌ | ❌ |
| `PUT /recipes/bulk/update` | `manager:recipes` | ✅ | ✅ | ❌ | ❌ |
| `PUT /recipes/bulk/activate` | `manager:recipes` | ✅ | ✅ | ❌ | ❌ |
| `POST /recipes/{id}/approve` | `manager:recipes` | ✅ | ✅ | ❌ | ❌ |
| `GET /recipes/public/{id}/nutrition` | None (Public) | ✅ | ✅ | ✅ | ✅ |

## Running the Tests

### Run all RBAC tests:
```bash
pytest modules/menu/tests/test_recipe_rbac.py -v
pytest modules/menu/tests/test_recipe_rbac_integration.py -v
```

### Run specific test class:
```bash
pytest modules/menu/tests/test_recipe_rbac.py::TestRecipeRBAC -v
```

### Run with coverage:
```bash
pytest modules/menu/tests/test_recipe_rbac*.py --cov=modules.menu.routes.recipe_routes
```

### Use the test runner:
```bash
python test_recipe_rbac_runner.py
```

## Test Scenarios Covered

1. **Basic Permission Checks**
   - Users with required permissions can access endpoints
   - Users without permissions receive 403 Forbidden
   - Unauthenticated requests receive 401 Unauthorized

2. **Admin-Only Operations**
   - Cost recalculation restricted to admins
   - Other roles cannot access admin endpoints

3. **Manager-Level Operations**
   - Bulk updates and approvals require manager role
   - Chefs and waiters cannot perform bulk operations

4. **Dry Run Operations**
   - Dry run still enforces permissions
   - Cannot simulate operations without proper permissions

5. **Public Endpoints**
   - Nutrition endpoint accessible without authentication
   - Returns appropriate data based on recipe status

6. **Error Handling**
   - Invalid tokens properly rejected
   - Missing authentication headers handled
   - Clear error messages for permission denials

## Adding New Tests

When adding new recipe endpoints, ensure you:
1. Add appropriate permission decorators
2. Create tests for each user role
3. Test both success and failure cases
4. Update the permission matrix documentation

## Best Practices

1. Always use the `require_permission` decorator on endpoints
2. Use specific permissions (e.g., `menu:create`) not generic ones
3. Admin users should have all permissions
4. Manager permissions should include staff operations
5. Public endpoints should validate data but not require auth