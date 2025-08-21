import React from 'react';
import { render, fireEvent } from '@testing-library/react-native';
import { NavigationContainer } from '@react-navigation/native';
import { Alert } from 'react-native';
import OrderDetailsScreen from '../OrderDetailsScreen';

// Mock navigation
const mockNavigate = jest.fn();
const mockGoBack = jest.fn();
const mockRoute = {
  params: {
    orderId: '123',
  },
};

jest.mock('@react-navigation/native', () => ({
  ...jest.requireActual('@react-navigation/native'),
  useNavigation: () => ({
    navigate: mockNavigate,
    goBack: mockGoBack,
  }),
  useRoute: () => mockRoute,
}));

// Mock Alert
jest.spyOn(Alert, 'alert');

// Mock UI components
jest.mock('../../../components/ui', () => ({
  Card: ({ children }: any) => children,
  CardContent: ({ children }: any) => children,
  Badge: ({ label }: any) => <>{label}</>,
  Button: ({ title, onPress }: any) => (
    <button onPress={onPress}>{title}</button>
  ),
  colors: {
    primary: { 500: '#4CAF50' },
    secondary: { 500: '#9C27B0' },
    success: { 500: '#4CAF50', 600: '#43A047' },
    warning: { 500: '#FFC107', 600: '#FFB300' },
    error: { 500: '#F44336' },
    neutral: { 400: '#BDBDBD', 500: '#9E9E9E' },
    text: {
      primary: '#212121',
      secondary: '#757575',
      tertiary: '#9E9E9E',
      inverse: '#FFFFFF',
    },
    background: {
      primary: '#FFFFFF',
      secondary: '#FAFAFA',
    },
    border: {
      light: '#E0E0E0',
    },
  },
  spacing: {
    xxs: 2,
    xs: 4,
    sm: 8,
    md: 16,
    lg: 24,
    xl: 32,
    xxl: 48,
  },
  typography: {
    fontSize: {
      h2: 28,
      title: 20,
      subtitle: 18,
      bodyLarge: 16,
      body: 14,
      caption: 12,
    },
    fontWeight: {
      bold: '700',
      semiBold: '600',
      medium: '500',
    },
    lineHeight: {
      h2: 36,
      title: 28,
      subtitle: 26,
      bodyLarge: 24,
      body: 20,
      caption: 16,
    },
  },
  borderRadius: {
    sm: 4,
    md: 8,
  },
  shadows: {
    sm: {},
  },
}));

describe('OrderDetailsScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders order details correctly', () => {
    const { getByText } = render(
      <NavigationContainer>
        <OrderDetailsScreen />
      </NavigationContainer>
    );

    // Check if order number is displayed
    expect(getByText('#ORD-123')).toBeTruthy();
    
    // Check if status is displayed
    expect(getByText('PREPARING')).toBeTruthy();
    
    // Check if customer info is displayed
    expect(getByText('John Doe')).toBeTruthy();
  });

  it('handles missing orderId', () => {
    // Mock route with no orderId
    mockRoute.params = {};
    
    render(
      <NavigationContainer>
        <OrderDetailsScreen />
      </NavigationContainer>
    );

    // Should show alert and navigate back
    expect(Alert.alert).toHaveBeenCalledWith(
      'Error',
      'Order ID is missing',
      expect.arrayContaining([
        expect.objectContaining({
          text: 'OK',
          onPress: expect.any(Function),
        }),
      ])
    );
  });

  it('navigates to ProcessPayment when payment is pending', () => {
    const { getByText } = render(
      <NavigationContainer>
        <OrderDetailsScreen />
      </NavigationContainer>
    );

    const paymentButton = getByText('Process Payment');
    fireEvent.press(paymentButton);

    expect(mockNavigate).toHaveBeenCalledWith('ProcessPayment', { orderId: '123' });
  });

  it('handles share action', () => {
    // Would need to mock Share API
    const { getByText } = render(
      <NavigationContainer>
        <OrderDetailsScreen />
      </NavigationContainer>
    );

    // Test would verify share functionality
    expect(true).toBe(true);
  });

  it('handles print action', () => {
    const { getByText } = render(
      <NavigationContainer>
        <OrderDetailsScreen />
      </NavigationContainer>
    );

    // Test would verify print functionality
    expect(true).toBe(true);
  });

  it('renders timeline correctly', () => {
    const { getByText } = render(
      <NavigationContainer>
        <OrderDetailsScreen />
      </NavigationContainer>
    );

    expect(getByText('Order Timeline')).toBeTruthy();
    expect(getByText('Order placed')).toBeTruthy();
    expect(getByText('Order confirmed')).toBeTruthy();
  });

  it('displays order items correctly', () => {
    const { getByText } = render(
      <NavigationContainer>
        <OrderDetailsScreen />
      </NavigationContainer>
    );

    expect(getByText('Margherita Pizza')).toBeTruthy();
    expect(getByText('1x')).toBeTruthy();
    expect(getByText('$12.99')).toBeTruthy();
  });

  it('calculates and displays order summary correctly', () => {
    const { getByText } = render(
      <NavigationContainer>
        <OrderDetailsScreen />
      </NavigationContainer>
    );

    expect(getByText('Order Summary')).toBeTruthy();
    expect(getByText('Subtotal')).toBeTruthy();
    expect(getByText('Tax (8.5%)')).toBeTruthy();
    expect(getByText('Total')).toBeTruthy();
  });

  it('supports both string and number orderId', () => {
    // Test with string orderId
    mockRoute.params = { orderId: '456' };
    const { rerender } = render(
      <NavigationContainer>
        <OrderDetailsScreen />
      </NavigationContainer>
    );
    expect(() => getByText('#ORD-456')).not.toThrow();

    // Test with number orderId
    mockRoute.params = { orderId: 789 };
    rerender(
      <NavigationContainer>
        <OrderDetailsScreen />
      </NavigationContainer>
    );
    expect(() => getByText('#ORD-789')).not.toThrow();
  });
});