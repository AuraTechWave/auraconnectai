# Frontend-Backend Integration Guide

## Overview
This guide documents the integration between the AuraConnect frontend (React) and backend (FastAPI).

## Quick Start

### Starting Both Services
```bash
# Run the provided script to start both services
./start-services.sh
```

This will:
- Start the backend on http://localhost:8000
- Start the frontend on http://localhost:3000
- API documentation available at http://localhost:8000/docs

### Manual Start

#### Backend
```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend
```bash
cd frontend
npm install
npm start
```

## Authentication Flow

### Login Process
1. User enters credentials on login page
2. Frontend sends POST to `/auth/login` with form data
3. Backend returns JWT tokens (access & refresh)
4. Tokens stored in localStorage
5. All subsequent requests include Authorization header

### Test Credentials
- **Admin**: username=`admin`, password=`secret`
- **Manager**: username=`manager`, password=`secret`
- **Payroll Clerk**: username=`payroll_clerk`, password=`secret`

## API Integration

### API Client Setup
The frontend uses an Axios interceptor (`frontend/src/utils/authInterceptor.js`) that:
- Automatically adds JWT token to requests
- Handles token refresh on 401 errors
- Manages logout on authentication failures

### Example API Usage
```javascript
import apiClient from '../utils/authInterceptor';

// GET request
const response = await apiClient.get('/settings/pos-sync');
const data = response.data;

// POST request
await apiClient.post('/settings/pos-sync', {
  tenant_id: 1,
  enabled: true
});
```

## Components Updated

### Core Components
1. **App.js** - Main app with authentication state
2. **Login.js** - Login form component
3. **AdminSettings.js** - POS sync settings management

### Dashboard Components
1. **ExternalPOSWebhookDashboard.tsx** - Webhook monitoring
2. **SyncStatusDashboard.tsx** - Order sync status

### Utilities
1. **authInterceptor.js** - Axios client with auth handling

## Environment Configuration

### Frontend (.env)
```
REACT_APP_API_URL=http://localhost:8000
REACT_APP_WS_URL=ws://localhost:8000
REACT_APP_ENV=development
```

### Backend
- CORS configured for http://localhost:3000
- JWT authentication enabled
- Rate limiting active

## Common Issues & Solutions

### CORS Errors
- Ensure backend is running before frontend
- Check CORS origins in `backend/app/main.py`

### Authentication Errors
- Clear localStorage and login again
- Check JWT token expiration settings

### API Connection Failed
- Verify backend is running on port 8000
- Check REACT_APP_API_URL in .env file

## Next Steps

1. **Add Error Boundaries** - Implement React error boundaries for better error handling
2. **Add Loading States** - Improve UX with proper loading indicators
3. **Implement Token Refresh** - Complete the token refresh logic in authInterceptor
4. **Add Request Retry** - Implement exponential backoff for failed requests
5. **WebSocket Integration** - Set up real-time updates for order tracking

## Development Tips

- Use the Swagger UI at http://localhost:8000/docs to test API endpoints
- Monitor Network tab in browser DevTools to debug API calls
- Check backend logs for detailed error messages
- Use React DevTools to inspect component state