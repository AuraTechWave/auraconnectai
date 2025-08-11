# Follow-up Ticket: Module Structure Standardization

## Title
Standardize Module Structure Across All Backend Modules

## Priority
Medium

## Labels
- technical-debt
- refactoring
- developer-experience

## Description
Following the implementation of insights, settings, and loyalty modules (AUR-371), we need to standardize the structure across all backend modules for consistency and maintainability.

## Current State Analysis

### Inconsistent Naming
1. **Routes vs Routers**:
   - Uses `routes/`: insights, loyalty, settings, equipment, menu, orders, payroll, pos, staff, tax
   - Uses `routers/`: analytics, customers, feedback, promotions, tables
   - Has both: orders, staff

2. **Service vs Services**:
   - Most use `services/`
   - Some use `controllers/` (orders, settings, staff, tax)

3. **Model vs Models**:
   - Consistent use of `models/` (good!)

### Inconsistent Structure Depth
1. **Well-structured modules** (multiple subfolders):
   - analytics, ai_recommendations, menu, orders, payments, staff

2. **Minimal structure** (just models/routes/schemas):
   - inventory, tax, tables

3. **Missing standard components**:
   - No `__init__.py` in some modules
   - No tests folder in some modules
   - No schemas in some modules

## Proposed Standard Structure

```
module_name/
├── __init__.py              # Module exports
├── models/                  # SQLAlchemy models
│   ├── __init__.py
│   └── *.py
├── schemas/                 # Pydantic schemas
│   ├── __init__.py
│   └── *.py
├── services/               # Business logic
│   ├── __init__.py
│   └── *.py
├── routes/                 # FastAPI routes (not routers!)
│   ├── __init__.py
│   └── *.py
├── tests/                  # Module tests
│   ├── __init__.py
│   ├── test_services.py
│   └── test_routes.py
├── utils/                  # Module-specific utilities (optional)
│   ├── __init__.py
│   └── *.py
└── docs/                   # Module documentation (optional)
    └── README.md
```

## Tasks

### Phase 1: Analysis (1 day)
- [ ] Create spreadsheet of all modules and their current structure
- [ ] Identify modules that need the most work
- [ ] Estimate effort for each module

### Phase 2: Standardization Plan (1 day)
- [ ] Create migration script to rename folders
- [ ] Create template for new modules
- [ ] Document standard in developer guide

### Phase 3: Implementation (5-7 days)
- [ ] Start with smallest modules (tables, tax)
- [ ] Standardize folder names:
  - [ ] Rename all `routers/` to `routes/`
  - [ ] Rename all `controllers/` to `services/`
- [ ] Add missing `__init__.py` files
- [ ] Add missing test folders
- [ ] Update imports in affected files

### Phase 4: Testing & Documentation (2 days)
- [ ] Run all tests
- [ ] Update import statements
- [ ] Update documentation
- [ ] Create module creation script

## Modules to Refactor (Priority Order)

### High Priority (Simple modules, quick wins):
1. **tax** - Add tests, standardize structure
2. **tables** - Rename routers → routes
3. **inventory** - Add services layer, tests

### Medium Priority (Moderate complexity):
4. **customers** - Rename routers → routes
5. **feedback** - Rename routers → routes  
6. **promotions** - Rename routers → routes
7. **equipment** - Already good, just needs tests

### Low Priority (Complex, working well):
8. **orders** - Remove controllers, consolidate routes/routers
9. **staff** - Remove controllers, consolidate routes/routers
10. **payments** - Well structured, maybe just documentation

## Success Criteria
- [ ] All modules follow the same folder structure
- [ ] All modules have tests
- [ ] Developer can create new module from template
- [ ] CI/CD passes for all modules
- [ ] Documentation updated

## Risks
- Import path changes may break existing code
- Merge conflicts with active development
- Time investment vs immediate value

## Mitigation
- Use automated refactoring tools
- Coordinate with team on timing
- Do modules in small batches
- Keep changes purely structural (no logic changes)

## Dependencies
- Completion of AUR-371 (insights, settings, loyalty modules)
- No active PRs on target modules

## Estimate
- Total: 8-10 days
- Can be done incrementally

## Benefits
1. **Developer Experience**: Consistent structure makes navigation easier
2. **Onboarding**: New developers learn one pattern
3. **Tooling**: Scripts and generators work uniformly
4. **Testing**: Consistent test structure and coverage
5. **Maintenance**: Easier to find and fix issues

## Implementation Script Example

```python
#!/usr/bin/env python3
"""Module standardization script"""

import os
import shutil
from pathlib import Path

def standardize_module(module_path: Path):
    """Standardize a single module structure"""
    
    # Rename routers to routes
    if (module_path / "routers").exists():
        shutil.move(module_path / "routers", module_path / "routes")
        print(f"Renamed routers → routes in {module_path.name}")
    
    # Rename controllers to services  
    if (module_path / "controllers").exists():
        shutil.move(module_path / "controllers", module_path / "services")
        print(f"Renamed controllers → services in {module_path.name}")
    
    # Create missing directories
    for folder in ["models", "schemas", "services", "routes", "tests"]:
        folder_path = module_path / folder
        if not folder_path.exists():
            folder_path.mkdir()
            (folder_path / "__init__.py").touch()
            print(f"Created {folder} in {module_path.name}")
    
    # Ensure __init__.py exists
    if not (module_path / "__init__.py").exists():
        (module_path / "__init__.py").touch()
        print(f"Created __init__.py in {module_path.name}")

if __name__ == "__main__":
    modules_dir = Path("backend/modules")
    for module in modules_dir.iterdir():
        if module.is_dir() and not module.name.startswith("."):
            standardize_module(module)
```

## Next Steps
1. Review and approve this plan
2. Create Linear ticket with this content
3. Schedule work for next sprint
4. Assign to backend team member