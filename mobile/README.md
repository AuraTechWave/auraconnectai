# AuraConnect Mobile App

React Native mobile application for AuraConnect Restaurant Management System.

## Features

- **Authentication & Security**
  - Secure login with JWT tokens
  - Biometric authentication support
  - Token refresh mechanism
  - Secure credential storage using Keychain

- **Offline Support**
  - Queue requests when offline
  - Automatic sync when connection restored
  - Local data persistence with MMKV
  - Network status monitoring

- **Navigation**
  - Tab navigation for main features
  - Stack navigation for detailed views
  - Drawer navigation for settings
  - Deep linking support

- **State Management**
  - Zustand for global state
  - React Query for server state
  - MMKV for persistent storage

## Tech Stack

- **React Native** 0.72.7
- **TypeScript** 4.8.4
- **React Navigation** 6.x
- **React Query** 5.x
- **Zustand** 4.x
- **React Native Paper** 5.x (Material Design)
- **React Hook Form** 7.x
- **Axios** for API calls
- **React Native MMKV** for storage
- **React Native Keychain** for secure storage

## Prerequisites

- Node.js >= 16
- Yarn or npm
- React Native development environment set up
- iOS: Xcode 14+ and CocoaPods
- Android: Android Studio and Android SDK

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/auraconnectai.git
cd auraconnectai/mobile
```

2. Install dependencies:
```bash
yarn install
# or
npm install
```

3. Install iOS dependencies:
```bash
cd ios && pod install
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

## Running the App

### iOS
```bash
yarn ios
# or
npx react-native run-ios
```

### Android
```bash
yarn android
# or
npx react-native run-android
```

### Metro Bundler
```bash
yarn start
# or
npx react-native start
```

## Project Structure

```
mobile/
├── src/
│   ├── App.tsx                 # Main app component
│   ├── components/             # Reusable components
│   │   ├── common/            # Common UI components
│   │   └── navigation/        # Navigation components
│   ├── contexts/              # React contexts
│   ├── hooks/                 # Custom hooks
│   ├── navigation/            # Navigation configuration
│   ├── screens/               # Screen components
│   │   ├── auth/             # Authentication screens
│   │   ├── dashboard/        # Dashboard screen
│   │   ├── orders/           # Order management
│   │   ├── staff/            # Staff management
│   │   ├── menu/             # Menu management
│   │   └── analytics/        # Analytics screens
│   ├── services/              # API and business logic
│   ├── store/                 # Global state management
│   ├── types/                 # TypeScript types
│   ├── utils/                 # Utility functions
│   └── constants/             # App constants
├── ios/                       # iOS specific files
├── android/                   # Android specific files
└── __tests__/                # Test files
```

## Key Components

### Authentication Flow
- Login screen with form validation
- Forgot password flow
- Secure token storage
- Auto token refresh

### Offline Support
- Network status monitoring
- Request queue management
- Automatic sync on reconnection
- Local data caching

### API Integration
- Centralized API client
- Request/response interceptors
- Error handling
- Token management

## Available Scripts

- `yarn android` - Run on Android
- `yarn ios` - Run on iOS
- `yarn start` - Start Metro bundler
- `yarn test` - Run tests
- `yarn lint` - Run ESLint
- `yarn lint:fix` - Fix ESLint issues
- `yarn typecheck` - Run TypeScript type checking

## Environment Configuration

Create a `.env` file based on `.env.example`:

```env
API_URL=https://api.auraconnect.ai/api
ENVIRONMENT=development
DEBUG_MODE=true
```

## Building for Production

### iOS
1. Open `ios/AuraConnectMobile.xcworkspace` in Xcode
2. Select proper signing team
3. Archive and distribute

### Android
```bash
cd android
./gradlew assembleRelease
# APK will be in android/app/build/outputs/apk/release/
```

## Troubleshooting

### iOS Build Issues
```bash
cd ios
pod deintegrate
pod install
```

### Android Build Issues
```bash
cd android
./gradlew clean
cd ..
npx react-native run-android
```

### Metro Bundler Issues
```bash
npx react-native start --reset-cache
```

## Contributing

1. Create a feature branch
2. Make your changes
3. Run tests and linting
4. Submit a pull request

## License

Proprietary - AuraConnect AI