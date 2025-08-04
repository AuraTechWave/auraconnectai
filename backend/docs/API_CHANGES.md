# API Changes Documentation

## Overview

This document outlines the recent changes to the AuraConnect Backend API following the compatibility fixes and refactoring.

## Import Path Changes

All import paths have been updated to remove the `backend.` prefix. This affects:
- Module imports throughout the codebase
- No external API impact - all endpoints remain the same

## Authentication Changes

### User Model
- `RBACUser` has been replaced with `User` throughout the API
- The response structure remains the same
- Authentication endpoints continue to work as before

### Permission System
- `get_current_staff_user` has been replaced with `get_current_user`
- Permission checks now use the updated `require_permission` dependency

## Exception Handling

### New Consistent Error Responses

All API errors now follow a consistent format:

```json
{
  "detail": "Error message",
  "error_code": "ERROR_CODE", 
  "path": "/api/endpoint/path"
}
```

### Error Code Mapping

| Python Exception | HTTP Status | Error Code |
|-----------------|-------------|------------|
| KeyError | 404 | NOT_FOUND |
| ValueError | 400 | VALIDATION_ERROR |
| PermissionError | 403 | PERMISSION_DENIED |

### Custom Exceptions

The following custom exceptions are available:
- `NotFoundError` - 404 responses
- `ValidationError` - 400 responses  
- `AuthenticationError` - 401 responses
- `PermissionError` - 403 responses
- `ConflictError` - 409 responses

## New Endpoints

### Reservations API (`/api/v1/reservations`)

New customer-facing reservation endpoints:

#### Create Reservation
- **POST** `/api/v1/reservations/`
- **Auth**: Customer token required
- **Body**: `ReservationCreate` schema

#### List Reservations
- **GET** `/api/v1/reservations/`
- **Auth**: Customer token required
- **Query params**: 
  - `status`: Filter by status
  - `from_date`: Start date filter
  - `to_date`: End date filter
  - `skip`: Pagination offset
  - `limit`: Page size

#### Get Reservation
- **GET** `/api/v1/reservations/{reservation_id}`
- **Auth**: Customer token required

#### Update Reservation
- **PUT** `/api/v1/reservations/{reservation_id}`
- **Auth**: Customer token required
- **Body**: `ReservationUpdate` schema

#### Cancel Reservation
- **POST** `/api/v1/reservations/{reservation_id}/cancel`
- **Auth**: Customer token required
- **Body**: `ReservationCancellation` schema

#### Check Availability
- **GET** `/api/v1/reservations/availability`
- **Auth**: Optional
- **Query params**:
  - `date`: Check date
  - `party_size`: Number of guests
  - `time_slot`: Optional specific time

## Environment Configuration

### Required Environment Variables

For **Production**:
```env
ENVIRONMENT=production
REDIS_URL=redis://your-redis-host:6379
SECRET_KEY=your-production-secret-key
SESSION_SECRET=your-production-session-secret
ALLOW_INSECURE_HTTP=false
```

For **Development**:
```env
ENVIRONMENT=development
# REDIS_URL is optional - will use in-memory fallback
SECRET_KEY=dev-secret-key-change-in-production
SESSION_SECRET=dev-secret-change-in-production
ALLOW_INSECURE_HTTP=true
```

### Startup Validation

The application now performs comprehensive startup checks:
1. Environment configuration validation
2. Database connectivity check
3. Redis connectivity check (required for production)
4. Database table existence verification

## Migration Notes

### For Existing Integrations

1. **Import paths**: No changes needed for external API consumers
2. **Authentication**: Existing tokens continue to work
3. **Error handling**: Error response format is now consistent - update error parsing if needed

### Database Migrations

Run migrations after pulling the latest changes:
```bash
alembic upgrade head
```

## Breaking Changes

None for external API consumers. All changes are internal refactoring.

## Deprecation Notices

The following are deprecated and will be removed in future versions:
- Pydantic v1 style validators (migrate to v2 style)
- SQLAlchemy 1.x patterns (migrate to 2.x style)

## Support

For questions or issues related to these changes:
- GitHub Issues: https://github.com/AuraTechWave/auraconnectai/issues
- Email: support@auraconnect.ai