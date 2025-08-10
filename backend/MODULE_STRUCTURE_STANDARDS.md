# Module Structure Standards

## Overview

This document defines the standardized directory structure for all modules in the AuraConnect backend to ensure consistency and maintainability.

## Standard Module Structure

Every module in the `backend/modules/` directory should follow this structure:

```
modules/
└── module_name/
    ├── __init__.py          # Module exports and documentation
    ├── models/              # Database models
    │   ├── __init__.py
    │   └── module_models.py
    ├── schemas/             # Pydantic schemas for validation
    │   ├── __init__.py
    │   └── module_schemas.py
    ├── routes/              # API route definitions
    │   ├── __init__.py
    │   └── module_routes.py
    ├── services/            # Business logic
    │   ├── __init__.py
    │   └── module_service.py
    ├── tests/               # Unit and integration tests
    │   ├── __init__.py
    │   ├── conftest.py     # Pytest fixtures
    │   ├── test_models.py
    │   ├── test_routes.py
    │   ├── test_schemas.py
    │   └── test_service.py
    └── docs/                # Module-specific documentation (optional)
        └── README.md
```

## Directory Descriptions

### `__init__.py`
- Module-level exports
- Module documentation
- Should export commonly used components

Example:
```python
"""Module description"""

from .routes import router
from .services import ModuleService
from .models import MainModel
from .schemas import CreateSchema, UpdateSchema

__all__ = ["router", "ModuleService", "MainModel", "CreateSchema", "UpdateSchema"]
```

### `models/`
- SQLAlchemy database models
- Enum definitions
- Database-related constants

### `schemas/`
- Pydantic models for request/response validation
- Input validation schemas
- Output serialization schemas

### `routes/`
- FastAPI router definitions
- API endpoint implementations
- Request/response handling

### `services/`
- Business logic implementation
- Database operations
- External service integrations
- Complex calculations

### `tests/`
- Unit tests for individual components
- Integration tests for API endpoints
- Test fixtures and utilities

## Import Conventions

### Within Module
Use relative imports for intra-module references:
```python
# In routes/module_routes.py
from ..services import ModuleService
from ..schemas import CreateSchema, UpdateSchema
from ..models import MainModel
```

### Cross-Module
Use absolute imports for cross-module references:
```python
# In any file
from modules.auth.models import User
from modules.auth.permissions import check_permission
from core.database import get_db
```

## Naming Conventions

1. **Files**: Use snake_case with module prefix
   - `equipment_models.py`
   - `equipment_routes.py`
   - `equipment_service.py`

2. **Classes**: Use PascalCase
   - `EquipmentService`
   - `MaintenanceRecord`

3. **Functions**: Use snake_case
   - `create_equipment()`
   - `get_maintenance_records()`

4. **Constants**: Use UPPER_SNAKE_CASE
   - `MAX_RETRY_ATTEMPTS`
   - `DEFAULT_TIMEOUT`

## Migration Process

When migrating a module from flat to standard structure:

1. Create directory structure:
   ```bash
   mkdir -p models routes schemas services
   ```

2. Move files to appropriate directories:
   ```bash
   mv models.py models/module_models.py
   mv routes.py routes/module_routes.py
   mv schemas.py schemas/module_schemas.py
   mv service.py services/module_service.py
   ```

3. Update imports in moved files:
   - Change `.` imports to `..` for cross-directory imports
   - Update file header comments with new path

4. Create `__init__.py` files for each directory with appropriate exports

5. Update module's main `__init__.py` to export from subdirectories

6. Update external imports (e.g., in `main.py`)

7. Run tests to ensure functionality is preserved

## Benefits

1. **Consistency**: All modules follow the same pattern
2. **Discoverability**: Easy to find specific components
3. **Scalability**: Clear where to add new functionality
4. **Testing**: Organized test structure mirrors code structure
5. **Maintenance**: Easier to understand and modify code

## Examples of Well-Structured Modules

- `modules/kds/` - Kitchen Display System
- `modules/customers/` - Customer Management
- `modules/equipment/` - Equipment Management (after migration)

## Modules Requiring Migration

The following modules should be migrated to the standard structure:
- [x] `equipment/` - Completed
- [ ] Any other modules with flat structure

## Validation

To validate a module follows the standard structure:

```python
import os

def validate_module_structure(module_path):
    required_dirs = ['models', 'routes', 'schemas', 'services', 'tests']
    for dir_name in required_dirs:
        dir_path = os.path.join(module_path, dir_name)
        if not os.path.isdir(dir_path):
            return False, f"Missing {dir_name} directory"
        
        init_path = os.path.join(dir_path, '__init__.py')
        if not os.path.isfile(init_path):
            return False, f"Missing __init__.py in {dir_name}"
    
    return True, "Valid structure"
```

## Conclusion

Following this standardized structure ensures our codebase remains organized, maintainable, and scalable as the project grows.