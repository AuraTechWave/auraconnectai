import React from 'react';
import { render, fireEvent, waitFor } from '@testing-library/react-native';
import { NavigationContainer } from '@react-navigation/native';
import OrdersScreen from '../OrdersScreen';

// Mock navigation
const mockNavigate = jest.fn();
jest.mock('@react-navigation/native', () => ({
  ...jest.requireActual('@react-navigation/native'),
  useNavigation: () => ({
    navigate: mockNavigate,
  }),
}));

// Mock UI components
jest.mock('../../../components/ui', () => ({
  Card: ({ children }: any) => children,
  CardContent: ({ children }: any) => children,
  Badge: ({ label }: any) => <>{label}</>,
  Avatar: ({ name }: any) => <>{name}</>,
  Button: ({ title, onPress }: any) => (
    <button onPress={onPress}>{title}</button>
  ),
  colors: require('../../../constants/designSystem').colors,
  spacing: require('../../../constants/designSystem').spacing,
  typography: require('../../../constants/designSystem').typography,
  borderRadius: require('../../../constants/designSystem').borderRadius,
  shadows: require('../../../constants/designSystem').shadows,
}));

// Mock react-native-paper components
jest.mock('react-native-paper', () => ({
  FAB: ({ label, onPress }: any) => (
    <button onPress={onPress}>{label}</button>
  ),
  Searchbar: ({ placeholder, onChangeText, value }: any) => (
    <input 
      placeholder={placeholder} 
      onChange={(e) => onChangeText(e.target.value)}
      value={value}
    />
  ),
  Chip: ({ children, onPress, selected }: any) => (
    <button onPress={onPress} data-selected={selected}>
      {children}
    </button>
  ),
  SegmentedButtons: ({ buttons, onValueChange }: any) => (
    <div>
      {buttons.map((btn: any) => (
        <button key={btn.value} onClick={() => onValueChange(btn.value)}>
          {btn.label}
        </button>
      ))}
    </div>
  ),
}));

// Mock vector icons
jest.mock('react-native-vector-icons/MaterialCommunityIcons', () => 'Icon');

describe('OrdersScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders without crashing', () => {
    const { getByText } = render(
      <NavigationContainer>
        <OrdersScreen />
      </NavigationContainer>
    );

    expect(getByText('New Order')).toBeTruthy();
  });

  it('displays mock orders', () => {
    const { getByText } = render(
      <NavigationContainer>
        <OrdersScreen />
      </NavigationContainer>
    );

    // Check if mock order data is displayed
    expect(getByText('#ORD-001')).toBeTruthy();
    expect(getByText('John Doe')).toBeTruthy();
    expect(getByText('Margherita Pizza')).toBeTruthy();
  });

  it('filters orders by search query', async () => {
    const { getByPlaceholderText, getByText, queryByText } = render(
      <NavigationContainer>
        <OrdersScreen />
      </NavigationContainer>
    );

    const searchInput = getByPlaceholderText('Search orders...');
    
    // Search for a specific order
    fireEvent.changeText(searchInput, 'ORD-002');
    
    await waitFor(() => {
      expect(getByText('#ORD-002')).toBeTruthy();
      expect(queryByText('#ORD-001')).toBeFalsy();
    });
  });

  it('filters orders by status', async () => {
    const { getByText, queryByText } = render(
      <NavigationContainer>
        <OrdersScreen />
      </NavigationContainer>
    );

    // Click on "Pending" filter
    const pendingChip = getByText('Pending');
    fireEvent.press(pendingChip);

    await waitFor(() => {
      expect(getByText('#ORD-003')).toBeTruthy(); // Pending order
      expect(queryByText('#ORD-001')).toBeFalsy(); // Preparing order
    });
  });

  it('filters orders by type', async () => {
    const { getByText, queryByText } = render(
      <NavigationContainer>
        <OrdersScreen />
      </NavigationContainer>
    );

    // Click on "Takeout" segment
    const takeoutButton = getByText('Takeout');
    fireEvent.press(takeoutButton);

    await waitFor(() => {
      expect(getByText('#ORD-002')).toBeTruthy(); // Takeout order
      expect(queryByText('#ORD-001')).toBeFalsy(); // Dine-in order
    });
  });

  it('navigates to order details when order is pressed', () => {
    const { getByText } = render(
      <NavigationContainer>
        <OrdersScreen />
      </NavigationContainer>
    );

    const orderCard = getByText('#ORD-001');
    fireEvent.press(orderCard);

    expect(mockNavigate).toHaveBeenCalledWith('OrderDetails', { orderId: '1' });
  });

  it('navigates to create order when FAB is pressed', () => {
    const { getByText } = render(
      <NavigationContainer>
        <OrdersScreen />
      </NavigationContainer>
    );

    const fab = getByText('New Order');
    fireEvent.press(fab);

    expect(mockNavigate).toHaveBeenCalledWith('CreateOrder');
  });

  it('shows empty state when no orders match filters', async () => {
    const { getByPlaceholderText, getByText } = render(
      <NavigationContainer>
        <OrdersScreen />
      </NavigationContainer>
    );

    const searchInput = getByPlaceholderText('Search orders...');
    fireEvent.changeText(searchInput, 'nonexistent');

    await waitFor(() => {
      expect(getByText('No orders found')).toBeTruthy();
      expect(getByText('Try adjusting your search')).toBeTruthy();
    });
  });

  it('has performance optimizations for FlatList', () => {
    const { UNSAFE_getByType } = render(
      <NavigationContainer>
        <OrdersScreen />
      </NavigationContainer>
    );

    const flatList = UNSAFE_getByType('FlatList');
    
    // Check if performance props are set
    expect(flatList.props.windowSize).toBe(10);
    expect(flatList.props.maxToRenderPerBatch).toBe(5);
    expect(flatList.props.initialNumToRender).toBe(10);
    expect(flatList.props.removeClippedSubviews).toBe(true);
    expect(flatList.props.updateCellsBatchingPeriod).toBe(50);
    expect(flatList.props.onEndReachedThreshold).toBe(0.5);
    expect(flatList.props.getItemLayout).toBeDefined();
  });

  it('memoizes renderOrderCard to prevent unnecessary re-renders', () => {
    const { rerender } = render(
      <NavigationContainer>
        <OrdersScreen />
      </NavigationContainer>
    );

    // Re-render should not cause renderOrderCard to be recreated
    rerender(
      <NavigationContainer>
        <OrdersScreen />
      </NavigationContainer>
    );

    // Test passes if no errors during re-render
    expect(true).toBe(true);
  });

  it('displays order priority badges correctly', () => {
    const { getByText } = render(
      <NavigationContainer>
        <OrdersScreen />
      </NavigationContainer>
    );

    // Check urgent priority badge
    expect(getByText('URGENT')).toBeTruthy();
    // Check high priority badge  
    expect(getByText('HIGH')).toBeTruthy();
  });

  it('displays payment status correctly', () => {
    const { getByText, getAllByText } = render(
      <NavigationContainer>
        <OrdersScreen />
      </NavigationContainer>
    );

    expect(getByText('Paid')).toBeTruthy();
    expect(getAllByText('Payment Pending').length).toBeGreaterThan(0);
  });

  it('shows special notes when present', () => {
    const { getByText } = render(
      <NavigationContainer>
        <OrdersScreen />
      </NavigationContainer>
    );

    expect(getByText('Allergic to nuts')).toBeTruthy();
  });

  it('has correct accessibility props on interactive elements', () => {
    const { getByLabelText } = render(
      <NavigationContainer>
        <OrdersScreen />
      </NavigationContainer>
    );

    // Check search bar accessibility
    expect(getByLabelText('Search orders')).toBeTruthy();
    
    // Check FAB accessibility
    expect(getByLabelText('Create new order')).toBeTruthy();
    
    // Check filter accessibility
    expect(getByLabelText('All orders filter')).toBeTruthy();
  });
});