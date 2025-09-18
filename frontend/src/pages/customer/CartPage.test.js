import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import CartPage from './CartPage';
import useCartStore from '../../stores/useCartStore';
import useCustomerStore from '../../stores/useCustomerStore';
import { promotionsApi } from '../../services/api';

// Mock the stores
jest.mock('../../stores/useCartStore');
jest.mock('../../stores/useCustomerStore');

// Mock the API
jest.mock('../../services/api');

// Mock react-router-dom
const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => mockNavigate
}));

// Mock CartItem component
jest.mock('../../components/customer/CartItem', () => {
  return function CartItem({ item, onUpdateQuantity, onRemove }) {
    return (
      <div data-testid={`cart-item-${item.cartId}`} className="cart-item-mock">
        <span>{item.name}</span>
        <span>${item.price}</span>
        <span>Qty: {item.quantity}</span>
        <button onClick={() => onUpdateQuantity(item.cartId, item.quantity + 1)}>
          +
        </button>
        <button onClick={() => onUpdateQuantity(item.cartId, item.quantity - 1)}>
          -
        </button>
        <button onClick={() => onRemove(item.cartId)}>
          Remove
        </button>
      </div>
    );
  };
});

const renderWithRouter = (component) => {
  return render(
    <BrowserRouter>
      {component}
    </BrowserRouter>
  );
};

describe('CartPage', () => {
  const mockCartStore = {
    items: [],
    getSubtotal: jest.fn().mockReturnValue(0),
    getTax: jest.fn().mockReturnValue(0),
    getTotal: jest.fn().mockReturnValue(0),
    clearCart: jest.fn(),
    setOrderType: jest.fn(),
    orderType: 'dine-in',
    setTableNumber: jest.fn(),
    tableNumber: null,
    setSpecialInstructions: jest.fn(),
    specialInstructions: '',
    appliedPromoCode: null,
    applyPromoCode: jest.fn(),
    removePromoCode: jest.fn(),
    discount: 0
  };

  const mockCustomerStore = {
    isAuthenticated: true
  };

  beforeEach(() => {
    useCartStore.mockReturnValue(mockCartStore);
    useCustomerStore.mockReturnValue(mockCustomerStore);
    mockNavigate.mockClear();
    
    // Clear all store method mocks
    Object.values(mockCartStore).forEach(fn => {
      if (typeof fn === 'function') fn.mockClear();
    });
  });

  describe('Empty Cart', () => {
    test('renders empty cart message when no items', () => {
      mockCartStore.items = [];
      
      renderWithRouter(<CartPage />);
      
      expect(screen.getByText('Your Cart is Empty')).toBeInTheDocument();
      expect(screen.getByText('Add some delicious items from our menu!')).toBeInTheDocument();
      expect(screen.getByText('Browse Menu')).toBeInTheDocument();
    });

    test('navigates to menu when browse menu button clicked', async () => {
      const user = userEvent.setup();
      mockCartStore.items = [];
      
      renderWithRouter(<CartPage />);
      
      const browseButton = screen.getByText('Browse Menu');
      await user.click(browseButton);
      
      expect(mockNavigate).toHaveBeenCalledWith('/menu');
    });

    test('applies empty cart styling', () => {
      mockCartStore.items = [];
      
      const { container } = renderWithRouter(<CartPage />);
      
      expect(container.querySelector('.cart-page.empty')).toBeInTheDocument();
    });
  });

  describe('Cart with Items', () => {
    const mockItems = [
      {
        cartId: 1,
        id: 1,
        name: 'Burger',
        price: 12.99,
        quantity: 2,
        modifiers: []
      },
      {
        cartId: 2,
        id: 2,
        name: 'Fries',
        price: 4.99,
        quantity: 1,
        modifiers: [{ name: 'Extra Salt', price: 0.50 }]
      }
    ];

    beforeEach(() => {
      mockCartStore.items = mockItems;
      mockCartStore.getSubtotal.mockReturnValue(30.97);
      mockCartStore.getTax.mockReturnValue(2.48);
      mockCartStore.getTotal.mockReturnValue(33.45);
    });

    test('renders cart items', () => {
      renderWithRouter(<CartPage />);
      
      expect(screen.getByText('Your Cart')).toBeInTheDocument();
      expect(screen.getByTestId('cart-item-1')).toBeInTheDocument();
      expect(screen.getByTestId('cart-item-2')).toBeInTheDocument();
    });

    test('displays order total calculations', () => {
      renderWithRouter(<CartPage />);
      
      expect(screen.getByText('$30.97')).toBeInTheDocument(); // Subtotal
      expect(screen.getByText('$2.48')).toBeInTheDocument();  // Tax
      expect(screen.getByText('$33.45')).toBeInTheDocument(); // Total
    });

    test('renders order type selector', () => {
      renderWithRouter(<CartPage />);
      
      expect(screen.getByText('Order Type')).toBeInTheDocument();
      expect(screen.getByText('Dine In')).toBeInTheDocument();
      expect(screen.getByText('Takeout')).toBeInTheDocument();
    });

    test('highlights selected order type', () => {
      mockCartStore.orderType = 'takeout';
      
      renderWithRouter(<CartPage />);
      
      const takeoutButton = screen.getByText('Takeout');
      expect(takeoutButton).toHaveClass('active');
    });

    test('changes order type when button clicked', async () => {
      const user = userEvent.setup();
      
      renderWithRouter(<CartPage />);
      
      const takeoutButton = screen.getByText('Takeout');
      await user.click(takeoutButton);
      
      expect(mockCartStore.setOrderType).toHaveBeenCalledWith('takeout');
    });

    test('shows table number input for dine-in orders', () => {
      mockCartStore.orderType = 'dine-in';
      
      renderWithRouter(<CartPage />);
      
      expect(screen.getByLabelText(/table number/i)).toBeInTheDocument();
    });

    test('updates table number', async () => {
      const user = userEvent.setup();
      mockCartStore.orderType = 'dine-in';
      
      renderWithRouter(<CartPage />);
      
      const tableInput = screen.getByLabelText(/table number/i);
      await user.type(tableInput, '5');
      
      expect(mockCartStore.setTableNumber).toHaveBeenCalledWith('5');
    });

    test('shows special instructions textarea', () => {
      renderWithRouter(<CartPage />);
      
      expect(screen.getByLabelText(/special instructions/i)).toBeInTheDocument();
    });

    test('updates special instructions', async () => {
      const user = userEvent.setup();
      
      renderWithRouter(<CartPage />);
      
      const instructionsInput = screen.getByLabelText(/special instructions/i);
      await user.type(instructionsInput, 'No onions please');
      
      expect(mockCartStore.setSpecialInstructions).toHaveBeenCalledWith('No onions please');
    });
  });

  describe('Promo Code Functionality', () => {
    beforeEach(() => {
      mockCartStore.items = [{
        cartId: 1,
        id: 1,
        name: 'Burger',
        price: 12.99,
        quantity: 1
      }];
      mockCartStore.getSubtotal.mockReturnValue(12.99);
      mockCartStore.getTotal.mockReturnValue(12.99);
    });

    test('renders promo code input section', () => {
      renderWithRouter(<CartPage />);
      
      expect(screen.getByText(/promo code/i)).toBeInTheDocument();
      expect(screen.getByPlaceholderText(/enter promo code/i)).toBeInTheDocument();
      expect(screen.getByText('Apply')).toBeInTheDocument();
    });

    test('updates promo code input value', async () => {
      const user = userEvent.setup();
      
      renderWithRouter(<CartPage />);
      
      const promoInput = screen.getByPlaceholderText(/enter promo code/i);
      await user.type(promoInput, 'SAVE10');
      
      expect(promoInput).toHaveValue('SAVE10');
    });

    test('applies valid promo code', async () => {
      const user = userEvent.setup();
      promotionsApi.validatePromoCode.mockResolvedValue({
        data: { valid: true, discount_amount: 5.00 }
      });
      
      renderWithRouter(<CartPage />);
      
      const promoInput = screen.getByPlaceholderText(/enter promo code/i);
      const applyButton = screen.getByText('Apply');
      
      await user.type(promoInput, 'SAVE5');
      await user.click(applyButton);
      
      await waitFor(() => {
        expect(promotionsApi.validatePromoCode).toHaveBeenCalledWith('SAVE5');
        expect(mockCartStore.applyPromoCode).toHaveBeenCalledWith('SAVE5', 5.00);
      });
    });

    test('shows error for invalid promo code', async () => {
      const user = userEvent.setup();
      promotionsApi.validatePromoCode.mockResolvedValue({
        data: { valid: false }
      });
      
      renderWithRouter(<CartPage />);
      
      const promoInput = screen.getByPlaceholderText(/enter promo code/i);
      const applyButton = screen.getByText('Apply');
      
      await user.type(promoInput, 'INVALID');
      await user.click(applyButton);
      
      await waitFor(() => {
        expect(screen.getByText('Invalid promo code')).toBeInTheDocument();
      });
    });

    test('shows error when API call fails', async () => {
      const user = userEvent.setup();
      promotionsApi.validatePromoCode.mockRejectedValue({
        response: { data: { message: 'Server error' } }
      });
      
      renderWithRouter(<CartPage />);
      
      const promoInput = screen.getByPlaceholderText(/enter promo code/i);
      const applyButton = screen.getByText('Apply');
      
      await user.type(promoInput, 'PROMO');
      await user.click(applyButton);
      
      await waitFor(() => {
        expect(screen.getByText('Server error')).toBeInTheDocument();
      });
    });

    test('shows applied promo code and remove option', () => {
      mockCartStore.appliedPromoCode = 'SAVE10';
      mockCartStore.discount = 10;
      
      renderWithRouter(<CartPage />);
      
      expect(screen.getByText('SAVE10')).toBeInTheDocument();
      expect(screen.getByText('Remove')).toBeInTheDocument();
      expect(screen.getByText('-$10.00')).toBeInTheDocument();
    });

    test('removes applied promo code', async () => {
      const user = userEvent.setup();
      mockCartStore.appliedPromoCode = 'SAVE10';
      mockCartStore.discount = 10;
      
      renderWithRouter(<CartPage />);
      
      const removeButton = screen.getByText('Remove');
      await user.click(removeButton);
      
      expect(mockCartStore.removePromoCode).toHaveBeenCalled();
    });

    test('does not apply empty promo code', async () => {
      const user = userEvent.setup();
      
      renderWithRouter(<CartPage />);
      
      const applyButton = screen.getByText('Apply');
      await user.click(applyButton);
      
      expect(promotionsApi.validatePromoCode).not.toHaveBeenCalled();
    });

    test('shows loading state while applying promo code', async () => {
      const user = userEvent.setup();
      let resolvePromo;
      promotionsApi.validatePromoCode.mockReturnValue(
        new Promise(resolve => { resolvePromo = resolve; })
      );
      
      renderWithRouter(<CartPage />);
      
      const promoInput = screen.getByPlaceholderText(/enter promo code/i);
      const applyButton = screen.getByText('Apply');
      
      await user.type(promoInput, 'LOADING');
      await user.click(applyButton);
      
      expect(applyButton).toBeDisabled();
      expect(screen.getByText('Applying...')).toBeInTheDocument();
      
      resolvePromo({ data: { valid: true, discount_amount: 5 } });
    });
  });

  describe('Checkout Flow', () => {
    beforeEach(() => {
      mockCartStore.items = [{
        cartId: 1,
        id: 1,
        name: 'Burger',
        price: 12.99,
        quantity: 1
      }];
    });

    test('renders checkout button', () => {
      renderWithRouter(<CartPage />);
      
      expect(screen.getByText('Proceed to Checkout')).toBeInTheDocument();
    });

    test('navigates to checkout when authenticated', async () => {
      const user = userEvent.setup();
      mockCustomerStore.isAuthenticated = true;
      
      renderWithRouter(<CartPage />);
      
      const checkoutButton = screen.getByText('Proceed to Checkout');
      await user.click(checkoutButton);
      
      expect(mockNavigate).toHaveBeenCalledWith('/checkout');
    });

    test('navigates to login when not authenticated', async () => {
      const user = userEvent.setup();
      mockCustomerStore.isAuthenticated = false;
      
      renderWithRouter(<CartPage />);
      
      const checkoutButton = screen.getByText('Proceed to Checkout');
      await user.click(checkoutButton);
      
      expect(mockNavigate).toHaveBeenCalledWith('/login', {
        state: { from: '/checkout' }
      });
    });

    test('clears cart when clear cart button clicked', async () => {
      const user = userEvent.setup();
      
      renderWithRouter(<CartPage />);
      
      const clearButton = screen.getByText('Clear Cart');
      await user.click(clearButton);
      
      expect(mockCartStore.clearCart).toHaveBeenCalled();
    });
  });

  describe('Cart Item Interactions', () => {
    beforeEach(() => {
      mockCartStore.items = [{
        cartId: 1,
        id: 1,
        name: 'Burger',
        price: 12.99,
        quantity: 2,
        modifiers: []
      }];
    });

    test('updates item quantity through CartItem component', async () => {
      const user = userEvent.setup();
      
      renderWithRouter(<CartPage />);
      
      const increaseButton = screen.getByText('+');
      await user.click(increaseButton);
      
      // This would be called by the CartItem component
      expect(mockCartStore.updateItemQuantity).toHaveBeenCalledWith(1, 3);
    });

    test('removes item through CartItem component', async () => {
      const user = userEvent.setup();
      
      renderWithRouter(<CartPage />);
      
      const removeButton = screen.getByText('Remove');
      await user.click(removeButton);
      
      // This would be called by the CartItem component
      expect(mockCartStore.removeItem).toHaveBeenCalledWith(1);
    });
  });
});