// Mock React Native modules
jest.mock('react-native/Libraries/Animated/NativeAnimatedHelper');
jest.mock('react-native-reanimated', () => {
  const Reanimated = require('react-native-reanimated/mock');
  Reanimated.default.call = () => {};
  return Reanimated;
});

// Mock gesture handler
jest.mock('react-native-gesture-handler', () => {
  const View = require('react-native/Libraries/Components/View/View');
  return {
    Swipeable: View,
    DrawerLayout: View,
    State: {},
    ScrollView: View,
    Slider: View,
    Switch: View,
    TextInput: View,
    ToolbarAndroid: View,
    ViewPagerAndroid: View,
    DrawerLayoutAndroid: View,
    WebView: View,
    NativeViewGestureHandler: View,
    TapGestureHandler: View,
    FlingGestureHandler: View,
    ForceTouchGestureHandler: View,
    LongPressGestureHandler: View,
    PanGestureHandler: View,
    PinchGestureHandler: View,
    RotationGestureHandler: View,
    RawButton: View,
    BaseButton: View,
    RectButton: View,
    BorderlessButton: View,
    FlatList: View,
    gestureHandlerRootHOC: jest.fn(component => component),
    Directions: {},
    GestureHandlerRootView: View,
  };
});

// Mock safe area context
jest.mock('react-native-safe-area-context', () => {
  const inset = { top: 0, right: 0, bottom: 0, left: 0 };
  return {
    SafeAreaProvider: ({ children }) => children,
    SafeAreaConsumer: ({ children }) => children(inset),
    SafeAreaView: ({ children }) => children,
    useSafeAreaInsets: () => inset,
  };
});

// Mock MMKV
jest.mock('react-native-mmkv', () => ({
  MMKV: jest.fn().mockImplementation(() => ({
    getString: jest.fn(),
    set: jest.fn(),
    delete: jest.fn(),
    clearAll: jest.fn(),
  })),
}));

// Mock Keychain
jest.mock('react-native-keychain', () => ({
  setInternetCredentials: jest.fn().mockResolvedValue(true),
  getInternetCredentials: jest.fn().mockResolvedValue({
    username: 'test',
    password: 'test-token',
  }),
  resetInternetCredentials: jest.fn().mockResolvedValue(true),
}));

// Mock NetInfo
jest.mock('@react-native-community/netinfo', () => ({
  addEventListener: jest.fn(),
  fetch: jest.fn().mockResolvedValue({ isConnected: true }),
}));

// Mock React Native Paper
jest.mock('react-native-paper', () => {
  const React = require('react');
  const { View, Text } = require('react-native');
  return {
    ...jest.requireActual('react-native-paper'),
    Portal: ({ children }) => children,
    Modal: ({ children }) => children,
  };
});

// Mock React Native Config
jest.mock('react-native-config', () => ({
  API_URL: 'https://api.test.com',
}));

// Mock React Native Toast Message
jest.mock('react-native-toast-message', () => ({
  show: jest.fn(),
}));

// Mock MaterialCommunityIcons
jest.mock('react-native-vector-icons/MaterialCommunityIcons', () => 'MaterialCommunityIcons');

// Silence the warning: Animated: `useNativeDriver` is not supported
jest.mock('react-native/Libraries/Animated/NativeAnimatedHelper');
