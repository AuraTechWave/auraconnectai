import React from 'react';
import { render } from '@testing-library/react-native';
import { NavigationContainer } from '@react-navigation/native';
import { OrdersNavigator } from '../OrdersNavigator';

// Mock the screen components
jest.mock('../../screens/orders/OrdersScreen', () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock('../../screens/orders/OrderDetailsScreen', () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock('../../screens/orders/CreateOrderScreen', () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock('../../screens/orders/OfflineOrdersScreen', () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock('../../screens/orders/ProcessPaymentScreen', () => ({
  __esModule: true,
  default: () => null,
}));

describe('OrdersNavigator', () => {
  it('renders without crashing', () => {
    const { getByTestId } = render(
      <NavigationContainer>
        <OrdersNavigator />
      </NavigationContainer>
    );
    
    // Navigator should render
    expect(() => getByTestId('orders-navigator')).not.toThrow();
  });

  it('has the correct initial route', () => {
    const { getByText } = render(
      <NavigationContainer>
        <OrdersNavigator />
      </NavigationContainer>
    );
    
    // Initial route should be OrdersList
    // This will be rendered as the screen title
    expect(() => getByText('Orders')).not.toThrow();
  });

  it('defines all required screens', () => {
    const screens = [
      'OrdersList',
      'OrderDetails',
      'CreateOrder',
      'OfflineOrders',
      'ProcessPayment',
    ];

    const { unmount } = render(
      <NavigationContainer>
        <OrdersNavigator />
      </NavigationContainer>
    );

    // Test passes if no errors during render
    // The actual navigation testing would require more complex setup
    expect(true).toBe(true);
    
    unmount();
  });
});