# AuraConnect Customer Web App

A modern, responsive web application for restaurant customers to browse menus, place orders, and make reservations.

## Features

- **Menu Browsing**: Browse restaurant menu with categories, search, and filters
- **Online Ordering**: Add items to cart with modifiers and special instructions
- **Reservations**: Make table reservations with date/time selection
- **User Authentication**: Register and login for personalized experience
- **Order History**: Track past orders and reorder favorites
- **Responsive Design**: Works seamlessly on desktop and mobile devices

## Tech Stack

- **React 18** with TypeScript
- **Material-UI (MUI)** for UI components
- **React Router** for navigation
- **React Query** for server state management
- **Zustand** for client state management
- **React Hook Form** for form handling
- **Axios** for API communication

## Prerequisites

- Node.js 16+ 
- npm or yarn
- Backend API running on http://localhost:8000

## Installation

1. Clone the repository:
```bash
git clone https://github.com/AuraTechWave/auraconnectai.git
cd auraconnectai/customer-web
```

2. Install dependencies:
```bash
npm install
```

3. Create a `.env` file:
```bash
REACT_APP_API_URL=http://localhost:8000/api/v1
```

## Development

Start the development server:
```bash
npm start
```

The app will run on http://localhost:3000

## Available Scripts

- `npm start` - Runs the app in development mode
- `npm test` - Launches the test runner
- `npm run build` - Builds the app for production
- `npm run lint` - Runs ESLint to check code quality

## Project Structure

```
src/
├── components/          # Reusable UI components
│   ├── auth/           # Authentication components
│   ├── menu/           # Menu browsing components
│   ├── orders/         # Order management components
│   ├── reservations/   # Reservation components
│   ├── common/         # Shared components
│   └── layout/         # Layout components
├── pages/              # Page components
├── services/           # API services
├── store/              # State management (Zustand)
├── hooks/              # Custom React hooks
├── types/              # TypeScript type definitions
└── utils/              # Utility functions
```

## Key Features Implementation

### Menu Browsing
- Category filtering
- Search functionality
- Dietary tags and allergen information
- Dynamic pricing with modifiers

### Shopping Cart
- Persistent cart storage
- Quantity management
- Special instructions per item
- Real-time total calculation

### Reservations
- Date and time selection
- Party size configuration
- Table preferences
- Special requests

### Authentication
- JWT-based authentication
- Secure password requirements
- Profile management
- Protected routes

## API Integration

The app integrates with the AuraConnect backend API for:
- Customer authentication
- Menu data
- Order management
- Reservation system
- User profiles

## Deployment

Build the production version:
```bash
npm run build
```

The build folder will contain optimized static files ready for deployment.

## Contributing

1. Create a feature branch
2. Make your changes
3. Run tests and linting
4. Submit a pull request

## License

This project is proprietary software owned by AuraTechWave.
