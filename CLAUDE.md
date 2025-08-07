# AuraConnect AI - Project Memory

## Project Overview
AuraConnect is an enterprise restaurant management platform built with modern architecture patterns. The system integrates order management, staff/payroll, tax compliance, POS integration, and AI-powered analytics.

## Tech Stack

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 14+ with Alembic migrations
- **Authentication**: JWT-based with refresh token rotation
- **Task Queue**: Background job processing
- **Caching**: Redis
- **Testing**: pytest with comprehensive test suites

### Frontend
- **React**: 18.2.0 with React Scripts
- **Build Tools**: ESLint, Prettier configured
- **Scripts**: `npm run lint`, `npm run build`, `npm run test`

### Mobile App
- **React Native**: 0.72.7
- **State Management**: Zustand
- **Data Fetching**: @tanstack/react-query
- **Offline DB**: WatermelonDB
- **Push Notifications**: Firebase + Notifee
- **Security**: react-native-keychain, crypto-js
- **Scripts**: `npm run lint`, `npm run typecheck`

## Project Structure

```
/auraconnectai/
   backend/          # FastAPI backend
      core/        # Core utilities (auth, db, config)
      modules/     # Feature modules
         analytics/
         auth/
         customers/
         feedback/
         inventory/
         loyalty/
         menu/
         orders/
         payroll/
         pos/
         promotions/
         staff/
         tax/
      alembic/     # Database migrations
   frontend/        # React web app
   mobile/          # React Native app
   docs/           # Documentation

```

## Key Features Implemented

1. **Order Management**
   - Real-time WebSocket support
   - Kitchen display integration
   - Payment reconciliation
   - Fraud detection
   - External POS webhooks

2. **Staff & Payroll**
   - Attendance tracking with SQL optimization
   - Enhanced payroll engine
   - Multi-jurisdiction tax calculation
   - Automated benefit proration
   - Comprehensive audit trails

3. **Tax Services**
   - IRS-compliant calculations
   - Social Security/Medicare caps
   - State/local tax support
   - W-2/1099 generation

4. **POS Integration**
   - Square, Clover, Toast adapters
   - Real-time sync with conflict resolution
   - Offline-first architecture
   - Automatic retry mechanisms

5. **Mobile Features (Recent)**
   - Comprehensive offline sync (AUR-310)
   - Push notifications for orders (AUR-311)
   - React Native foundation (AUR-309)

## Recent Development Focus

Based on recent commits, the team has been focused on:
- Mobile app development (offline sync, push notifications)
- Payroll & Tax module enhancements
- POS analytics and manual sync endpoints
- Comprehensive testing suites

## API Endpoints
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Development Commands

### Backend
```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
pytest  # Run tests
```

### Frontend
```bash
cd frontend
npm run lint
npm run build
npm run test
```

### Mobile
```bash
cd mobile
npm run lint
npm run typecheck
npm run ios  # or android
```

## Security Notes
- JWT tokens with type validation
- RBAC (Role-based access control)
- Tenant isolation for multi-restaurant
- Password security with Argon2

## Testing Strategy
- Unit tests for business logic
- Integration tests for APIs
- Performance tests for SQL
- Mock-based tests for external services

## Environment Variables Required
- JWT_SECRET_KEY
- DATABASE_URL
- REDIS_URL
- SMTP/Twilio/Firebase credentials for notifications

## Important Development Practices

### Branch Management
**ALWAYS work on issues in a fresh, up-to-date branch:**
```bash
# Before starting ANY issue or task:
git checkout main
git pull origin main
git checkout -b feature/AUR-XXX-brief-description

# NEVER work directly on main
# NEVER create a branch from another feature branch
# ALWAYS start from an updated main branch
```

This ensures:
- Clean separation of features
- Easy PR creation and review
- Avoids conflicts with main branch
- Maintains clean git history
- Prevents mixing unrelated changes
```

## Active Development Tasks

### Recipe (BOM) Management ✅ COMPLETED
- ✅ Recipe (Bill of Materials) management for menu items has been fully implemented
- ✅ Complete recipe feature with the following requirements:
  * ✅ Each menu item can be linked to multiple ingredients with specific quantities
  * ✅ APIs for CRUD operations on recipes are implemented
  * ✅ Validation ensures all active menu items have recipes configured
  * ✅ Integration with main.py completed

#### Features Implemented:
- Full CRUD operations for recipes
- Automatic cost calculation from inventory prices
- Sub-recipe support for complex items
- Recipe versioning with history tracking
- Compliance reporting for items without recipes
- Bulk operations for import/export
- Recipe cloning with portion adjustment
- Nutritional information tracking

#### Metadata
- URL: [https://linear.app/auraconnect/issue/AUR-359/finalize-recipe-bom-management-for-menu-items](https://linear.app/auraconnect/issue/AUR-359/finalize-recipe-bom-management-for-menu-items)
- Identifier: AUR-359
- Status: Completed
- Priority: No priority
- Assignee: Completed
- Created: 2025-08-02T16:49:05.731Z
- Updated: 2025-08-04T21:00:00.000Z
- Completed: 2025-08-04T21:00:00.000Z