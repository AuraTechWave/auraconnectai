# CI/CD Pipeline Setup

## Overview

AuraConnect uses GitHub Actions for continuous integration and deployment. The pipeline runs comprehensive tests for backend (Python), frontend (React), and documentation (MkDocs).

## Workflow File

**Location:** `.github/workflows/main.yml`

## Pipeline Jobs

### 1. Backend Tests & Linting (`backend-tests`)

**Environment:**
- Ubuntu Latest
- Python 3.11
- PostgreSQL 14 service

**Steps:**
1. **Setup**: Checkout code, setup Python with pip caching
2. **Dependencies**: Install `requirements.txt` + `requirements-dev.txt`
3. **Linting**: 
   - `flake8` with syntax error detection (E9,F63,F7,F82)
   - Non-blocking warnings for complexity/line length
4. **Import Testing**: Verify all critical module imports work
5. **Test Execution**: Run pytest on `modules/payroll/tests/`

**Key Environment Variables:**
- `PYTHONPATH`: Set to backend directory for proper imports
- `DATABASE_URL`: PostgreSQL connection for integration tests

### 2. Frontend Tests & Build (`frontend-tests`)

**Environment:**
- Ubuntu Latest  
- Node.js 18

**Steps:**
1. **Setup**: Checkout code, setup Node.js with npm caching
2. **Dependencies**: `npm ci` for consistent installs
3. **Testing**: `npm test` with coverage reporting
4. **Build**: `npm run build` to verify production builds

### 3. Documentation Build (`docs-build`)

**Environment:**
- Ubuntu Latest
- Python 3.11

**Steps:**
1. **Setup**: Checkout code, setup Python
2. **Dependencies**: Install MkDocs + Material theme
3. **Build**: `mkdocs build --strict` (fails on warnings)

### 4. Deployment (`deploy`)

**Conditions:**
- Only runs on `main` branch pushes
- Requires all other jobs to pass
- Currently just shows success notification

## Key Fixes Applied

### Previous Issues
- **Multiple conflicting workflows** running simultaneously
- **Wrong package managers** (yarn vs npm confusion)
- **Missing test execution** - only linted, never ran tests
- **Import path issues** causing ModuleNotFoundError
- **No database setup** for integration tests

### Solutions Implemented
- **Single comprehensive workflow** replacing 3+ conflicting ones
- **Proper Python path configuration** with `PYTHONPATH`  
- **Database service setup** for PostgreSQL-dependent tests
- **Correct package manager usage** (npm for frontend)
- **Enhanced dependencies** including pytest-mock, black, isort

## Local Development

### Backend Testing
```bash
cd backend
export PYTHONPATH="${PWD}:$PYTHONPATH"
pip install -r requirements.txt -r requirements-dev.txt
pytest modules/payroll/tests/ -v
```

### Frontend Testing
```bash
cd frontend
npm ci
npm test
npm run build
```

### Documentation
```bash
pip install mkdocs mkdocs-material
mkdocs build --strict
mkdocs serve  # for local preview
```

## Troubleshooting

### Common Issues

**1. Import Errors**
- Ensure `PYTHONPATH` includes backend directory
- Use absolute imports: `from modules.payroll.* import *`
- Check `__init__.py` files exist in all packages

**2. Database Connection Issues**
- Verify PostgreSQL service is running
- Check `DATABASE_URL` environment variable
- Ensure test database permissions are correct

**3. Frontend Build Failures**
- Clear npm cache: `npm cache clean --force`
- Delete `node_modules` and run `npm ci`
- Check Node.js version compatibility

**4. Linting Failures**
- Run `flake8 .` locally to see issues
- Use `black .` for automatic formatting
- Check line length limits (88 characters)

### Pipeline Debugging

```bash
# Test imports locally
cd backend
python -c "
from modules.payroll.services.payroll_tax_engine import PayrollTaxEngine
print('✅ Imports working')
"

# Test basic CI functionality
python test_basic_ci.py

# Run specific test files
pytest modules/payroll/tests/test_payroll_tax_engine.py -v
```

## Future Enhancements

- **Code Coverage Reports**: Upload to CodeCov or similar
- **Security Scanning**: Add Bandit, Safety checks
- **Performance Testing**: Load testing for APIs
- **Deployment Automation**: Actual deployment to staging/prod
- **Notification System**: Slack/Discord integration for build status

## Monitoring

The pipeline provides clear success/failure indicators:
- ✅ **Green checkmarks**: All tests passed
- ❌ **Red X marks**: Build failures with detailed logs
- 🟡 **Yellow warnings**: Non-blocking issues

Check the Actions tab in GitHub for detailed logs and timing information.