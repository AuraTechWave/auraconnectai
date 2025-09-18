# E2E Testing Guide

This document explains how to run End-to-End (E2E) tests for the AuraConnect frontend.

## Overview

The E2E tests use Playwright to test the frontend application. Tests can run in two modes:

1. **With Backend API** - Full integration tests against a running backend
2. **With Mocks** - Frontend-only tests using mocked API responses

## Quick Start

### Recommended: Run with Mocks (Development)

```bash
cd frontend
npm run test:e2e
```

This runs tests using mocked API responses. The tests marked as `*-with-mocks.spec.ts` and basic frontend tests will pass without requiring a backend server.

**Currently passing tests:**
- ✅ Frontend smoke tests (app loads, login page renders)
- ✅ Mocked authentication tests
- ✅ Basic navigation tests

**Tests requiring backend:** 
Most integration tests require a running backend API and will fail locally. These tests pass in CI/CD where the full backend is available.

### Alternative: Full Backend Setup (Advanced)

⚠️ **Note**: Due to backend complexity, running the full backend locally for E2E tests requires significant setup and may encounter dependency issues.

For advanced users who need full integration testing:

```bash
# Option 1: Using Docker (if you have all services configured)
./scripts/start-e2e-backend.sh

# Option 2: Quick SQLite setup (experimental)  
./scripts/quick-e2e-backend.sh
```

Then run tests:
```bash
cd frontend
npm run test:e2e
```

## Backend Setup Options

### Quick Setup (SQLite)
Uses SQLite database and minimal configuration:
```bash
./scripts/quick-e2e-backend.sh
```

### Full Setup (PostgreSQL + Redis)
Uses Docker to run full database services:
```bash
./scripts/start-e2e-backend.sh
```

To stop services:
```bash
./scripts/stop-e2e-backend.sh
```

## Available Test Commands

```bash
# Run all tests (default: chromium)
npm run test:e2e

# Run tests in specific browsers
npm run test:e2e:chromium
npm run test:e2e:firefox
npm run test:e2e:webkit

# Run tests with UI (interactive mode)
npm run test:e2e:ui

# Run tests in headed mode (see browser)
npm run test:e2e:headed

# Debug tests
npm run test:e2e:debug

# Generate test code
npm run test:e2e:codegen

# Show test report
npm run test:e2e:report
```

## Test Structure

```
e2e/
├── config/           # Test configuration
├── fixtures/         # Test data and fixtures
├── pages/           # Page Object Models
├── tests/           # Test files
│   ├── auth/        # Authentication tests
│   ├── orders/      # Order management tests
│   └── smoke.spec.ts # Basic smoke tests
└── utils/           # Test utilities
    └── mock-api.ts  # API mocking utilities
```

## Writing Tests

### With Mocks (Recommended)

```typescript
import { test, expect } from '@playwright/test';
import { MockAPI } from '../utils/mock-api';

test.describe('Feature Tests', () => {
  let mockAPI: MockAPI;

  test.beforeEach(async ({ page }) => {
    mockAPI = new MockAPI(page);
    await mockAPI.setupAllMocks();
  });

  test('should work with mocked API', async ({ page }) => {
    await page.goto('/');
    // Your test code here
  });
});
```

### With Real API

```typescript
import { test, expect } from '@playwright/test';

test.describe('Integration Tests', () => {
  test('should work with real API', async ({ page }) => {
    // These tests require backend to be running
    await page.goto('/');
    // Your test code here
  });
});
```

## Environment Variables

```bash
# Test Configuration
E2E_BASE_URL=http://localhost:3000
E2E_API_BASE_URL=http://localhost:8000

# Test Credentials
E2E_CUSTOMER_EMAIL=test.customer@example.com
E2E_CUSTOMER_PASSWORD=TestPass123!
E2E_STAFF_EMAIL=test.staff@example.com
E2E_STAFF_PASSWORD=TestPass123!
```

## Test Status Summary

**✅ Working (3 tests passing):**
- Basic frontend application loading
- Login page rendering and form functionality  
- Mocked API authentication flows

**⚠️ Expected Failures (93 tests):**
- Integration tests requiring live backend API
- Real authentication flows
- Database-dependent operations

This is **expected behavior** for local development. The failing tests require:
- PostgreSQL database
- Redis cache  
- Full backend server with all dependencies
- Test user accounts in database

These tests pass automatically in CI/CD where the full stack is available.

## Troubleshooting

### Tests Failing to Connect to Backend
This is expected! Most tests require a backend server.

**Solutions:**
1. **Recommended**: Use mocked tests (see `*-with-mocks.spec.ts` files)
2. **Advanced**: Set up full backend stack (see Backend Setup Options above)
3. **CI/CD**: Tests automatically pass in GitHub Actions with full stack

### Browser Not Found
```bash
cd frontend
npx playwright install
```

### Permission Errors
```bash
chmod +x scripts/*.sh
```

### Database Issues
```bash
# Stop and restart services
./scripts/stop-e2e-backend.sh
./scripts/start-e2e-backend.sh
```

## CI/CD

The E2E tests run automatically in GitHub Actions with:
- PostgreSQL and Redis services
- All three browsers (Chromium, Firefox, WebKit)
- Test artifacts and videos on failure

See `.github/workflows/e2e-tests.yml` for the full CI configuration.