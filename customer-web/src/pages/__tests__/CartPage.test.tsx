import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { CartPage } from '../CartPage';
import { useCartStore } from '../../store/cartStore';
import { useAuthStore } from '../../store/authStore';

jest.mock('../../store/cartStore');
jest.mock('../../store/authStore');

const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => mockNavigate,
}));

const mockCartItems = [
  {
    menuItem: {
      id: 1,
      name: 'Test Burger',
      price: 12.99,
      description: 'A delicious burger',
    },
    quantity: 2,
    subtotal: 25.98,
  },
  {
    menuItem: {
      id: 2,
      name: 'Test Salad',
      price: 8.99,
      description: 'A fresh salad',
    },
    quantity: 1,
    subtotal: 8.99,
  },
];

describe('CartPage', () => {
  const mockUpdateItemQuantity = jest.fn();
  const mockRemoveItem = jest.fn();
  const mockClearCart = jest.fn();
  const mockGetTotal = jest.fn(() => 34.97);

  beforeEach(() => {
    jest.clearAllMocks();
    (useCartStore as unknown as jest.Mock).mockReturnValue({
      items: mockCartItems,
      getTotal: mockGetTotal,
      updateItemQuantity: mockUpdateItemQuantity,
      removeItem: mockRemoveItem,
      clearCart: mockClearCart,
    });
    (useAuthStore as unknown as jest.Mock).mockReturnValue({
      isAuthenticated: true,
    });
  });

  const renderCartPage = () => {
    render(
      <BrowserRouter>
        <CartPage />
      </BrowserRouter>
    );
  };

  test('renders cart items', () => {
    renderCartPage();

    expect(screen.getByText('Test Burger')).toBeInTheDocument();
    expect(screen.getByText('Test Salad')).toBeInTheDocument();
    expect(screen.getByText('$25.98')).toBeInTheDocument();
    expect(screen.getByText('$8.99')).toBeInTheDocument();
  });

  test('updates item quantity', () => {
    renderCartPage();

    const increaseButtons = screen.getAllByLabelText('increase quantity');
    fireEvent.click(increaseButtons[0]);

    expect(mockUpdateItemQuantity).toHaveBeenCalledWith(1, 3);
  });

  test('removes item from cart', () => {
    renderCartPage();

    const deleteButtons = screen.getAllByLabelText('remove item');
    fireEvent.click(deleteButtons[0]);

    expect(mockRemoveItem).toHaveBeenCalledWith(1);
  });

  test('clears entire cart', () => {
    renderCartPage();

    const clearButton = screen.getByText(/clear cart/i);
    fireEvent.click(clearButton);

    expect(mockClearCart).toHaveBeenCalled();
  });

  test('shows empty cart message', () => {
    (useCartStore as unknown as jest.Mock).mockReturnValue({
      items: [],
      getTotal: jest.fn(() => 0),
      updateItemQuantity: mockUpdateItemQuantity,
      removeItem: mockRemoveItem,
      clearCart: mockClearCart,
    });

    renderCartPage();

    expect(screen.getByText(/your cart is empty/i)).toBeInTheDocument();
    expect(screen.getByText(/start shopping/i)).toBeInTheDocument();
  });

  test('calculates and displays totals correctly', () => {
    renderCartPage();

    // Subtotal
    expect(screen.getByText('$34.97')).toBeInTheDocument();
    
    // Tax (8.5%)
    expect(screen.getByText('$2.97')).toBeInTheDocument();
    
    // Total with delivery
    expect(screen.getByText('$39.94')).toBeInTheDocument();
  });

  test('navigates to checkout when authenticated', () => {
    renderCartPage();

    const checkoutButton = screen.getByText(/proceed to checkout/i);
    fireEvent.click(checkoutButton);

    expect(mockNavigate).toHaveBeenCalledWith('/checkout');
  });

  test('navigates to login when not authenticated', () => {
    (useAuthStore as unknown as jest.Mock).mockReturnValue({
      isAuthenticated: false,
    });

    renderCartPage();

    const checkoutButton = screen.getByText(/proceed to checkout/i);
    fireEvent.click(checkoutButton);

    expect(mockNavigate).toHaveBeenCalledWith('/login', {
      state: { from: '/checkout' },
    });
  });
});