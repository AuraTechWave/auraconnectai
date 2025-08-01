# AuraConnect Customer Web App

A modern, responsive web application for restaurant customers to browse menus, place orders, and make reservations.

## Features

- **User Authentication**: Register and login with JWT-based authentication
- **Menu Browsing**: Browse menu items by category with search functionality
- **Shopping Cart**: Add items to cart, adjust quantities, and checkout
- **Order Management**: Place orders, track order status, and view order history
- **Table Reservations**: Make and manage table reservations
- **Payment Processing**: Secure payment flow with demo payment integration
- **Responsive Design**: Works seamlessly on desktop and mobile devices

## Tech Stack

- **React 18** with TypeScript
- **Material-UI (MUI v5)** for UI components
- **React Router v6** for navigation
- **React Query** for server state management
- **Zustand** for client state management
- **React Hook Form** for form handling
- **Axios** for API communication
- **Jest & React Testing Library** for testing

## Getting Started

### Prerequisites

- Node.js 16+ and npm/yarn
- Backend API running (optional - app works with mock data)

### Installation

```bash
# Install dependencies
npm install

# Start development server
npm start

# Run on custom port
PORT=3001 npm start
```

### Available Scripts

- `npm start` - Start development server
- `npm test` - Run tests
- `npm run build` - Build for production
- `npm run lint` - Run ESLint

## Development

### Mock Data Mode

The app runs in mock data mode by default, allowing full functionality without the backend:

```typescript
// src/services/api.ts
const USE_MOCK_DATA = true; // Toggle this to use real API
```

### Demo Credentials

When in mock mode, use these credentials:
- Email: `demo@example.com`
- Password: `demo123`

### Environment Variables

Create a `.env` file in the root:

```env
REACT_APP_API_URL=http://localhost:8000/api/v1
```

## Project Structure

```
src/
├── components/       # Reusable UI components
│   ├── auth/        # Authentication components
│   ├── cart/        # Shopping cart components
│   ├── common/      # Common/shared components
│   ├── layout/      # Layout components
│   ├── menu/        # Menu-related components
│   └── payment/     # Payment components
├── pages/           # Page components
├── services/        # API services and mock data
├── store/           # Zustand stores
├── types/           # TypeScript type definitions
└── App.tsx          # Main app component
```

## API Integration

The app integrates with the following API endpoints:

### Customer Authentication
- `POST /customers/auth/register` - Register new customer
- `POST /customers/auth/login` - Customer login
- `POST /customers/auth/logout` - Customer logout

### Menu
- `GET /menu/public/categories` - Get menu categories
- `GET /menu/public/items` - Get menu items
- `GET /menu/public/items/:id` - Get item details

### Orders
- `POST /orders` - Create order
- `GET /orders/my-orders` - Get customer orders
- `GET /orders/:id` - Get order details

### Reservations
- `POST /reservations` - Create reservation
- `GET /reservations/my-reservations` - Get customer reservations
- `PUT /reservations/:id` - Update reservation
- `POST /reservations/:id/cancel` - Cancel reservation

## Testing

Run the test suite:

```bash
# Run all tests
npm test

# Run tests in watch mode
npm test -- --watchAll

# Run tests with coverage
npm test -- --coverage
```

## Deployment

Build the app for production:

```bash
npm run build
```

The build folder will contain the optimized production build.

## Contributing

1. Create a feature branch from `main`
2. Make your changes
3. Write/update tests
4. Ensure all tests pass
5. Submit a pull request

## License

This project is part of the AuraConnect restaurant management system.