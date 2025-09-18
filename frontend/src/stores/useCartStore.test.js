import { act, renderHook } from '@testing-library/react';
import useCartStore from './useCartStore';

// Mock zustand persist
jest.mock('zustand/middleware', () => ({
  persist: (config) => (set, get, api) => config(set, get, api),
  createJSONStorage: () => ({
    getItem: jest.fn(),
    setItem: jest.fn(),
    removeItem: jest.fn(),
  }),
}));

describe('useCartStore', () => {
  beforeEach(() => {
    // Reset store state before each test
    const { result } = renderHook(() => useCartStore());
    act(() => {
      result.current.clearCart();
    });
  });

  describe('Cart Items Management', () => {
    test('adds item to cart', () => {
      const { result } = renderHook(() => useCartStore());
      
      const item = {
        id: 1,
        name: 'Burger',
        price: 12.99,
        modifiers: []
      };

      act(() => {
        result.current.addItem(item);
      });

      expect(result.current.items).toHaveLength(1);
      expect(result.current.items[0]).toMatchObject({
        ...item,
        quantity: 1
      });
    });

    test('increments quantity for duplicate item', () => {
      const { result } = renderHook(() => useCartStore());
      
      const item = {
        id: 1,
        name: 'Burger',
        price: 12.99,
        modifiers: []
      };

      act(() => {
        result.current.addItem(item);
        result.current.addItem(item);
      });

      expect(result.current.items).toHaveLength(1);
      expect(result.current.items[0].quantity).toBe(2);
    });

    test('adds separate entries for items with different modifiers', () => {
      const { result } = renderHook(() => useCartStore());
      
      const item1 = {
        id: 1,
        name: 'Burger',
        price: 12.99,
        modifiers: []
      };
      
      const item2 = {
        id: 1,
        name: 'Burger',
        price: 12.99,
        modifiers: [{ id: 1, name: 'Extra Cheese', price: 1.50 }]
      };

      act(() => {
        result.current.addItem(item1);
        result.current.addItem(item2);
      });

      expect(result.current.items).toHaveLength(2);
    });

    test('updates item quantity', () => {
      const { result } = renderHook(() => useCartStore());
      
      const item = {
        id: 1,
        name: 'Burger',
        price: 12.99,
        modifiers: []
      };

      act(() => {
        result.current.addItem(item);
      });

      const cartId = result.current.items[0].cartId;

      act(() => {
        result.current.updateItemQuantity(cartId, 5);
      });

      expect(result.current.items[0].quantity).toBe(5);
    });

    test('removes item when quantity is set to 0', () => {
      const { result } = renderHook(() => useCartStore());
      
      const item = {
        id: 1,
        name: 'Burger',
        price: 12.99,
        modifiers: []
      };

      act(() => {
        result.current.addItem(item);
      });

      const cartId = result.current.items[0].cartId;

      act(() => {
        result.current.updateItemQuantity(cartId, 0);
      });

      expect(result.current.items).toHaveLength(0);
    });

    test('removes specific item from cart', () => {
      const { result } = renderHook(() => useCartStore());
      
      const item1 = { id: 1, name: 'Burger', price: 12.99, modifiers: [] };
      const item2 = { id: 2, name: 'Pizza', price: 15.99, modifiers: [] };

      act(() => {
        result.current.addItem(item1);
        result.current.addItem(item2);
      });

      const cartId = result.current.items[0].cartId;

      act(() => {
        result.current.removeItem(cartId);
      });

      expect(result.current.items).toHaveLength(1);
      expect(result.current.items[0].name).toBe('Pizza');
    });

    test('clears entire cart', () => {
      const { result } = renderHook(() => useCartStore());
      
      act(() => {
        result.current.addItem({ id: 1, name: 'Burger', price: 12.99 });
        result.current.addItem({ id: 2, name: 'Pizza', price: 15.99 });
        result.current.setTableNumber(5);
        result.current.setSpecialInstructions('No onions');
      });

      act(() => {
        result.current.clearCart();
      });

      expect(result.current.items).toHaveLength(0);
      expect(result.current.tableNumber).toBeNull();
      expect(result.current.specialInstructions).toBe('');
      expect(result.current.discount).toBe(0);
    });
  });

  describe('Cart Settings', () => {
    test('sets order type', () => {
      const { result } = renderHook(() => useCartStore());

      act(() => {
        result.current.setOrderType('takeout');
      });

      expect(result.current.orderType).toBe('takeout');
    });

    test('sets table number', () => {
      const { result } = renderHook(() => useCartStore());

      act(() => {
        result.current.setTableNumber(5);
      });

      expect(result.current.tableNumber).toBe(5);
    });

    test('sets special instructions', () => {
      const { result } = renderHook(() => useCartStore());

      act(() => {
        result.current.setSpecialInstructions('No onions, extra sauce');
      });

      expect(result.current.specialInstructions).toBe('No onions, extra sauce');
    });

    test('sets restaurant ID', () => {
      const { result } = renderHook(() => useCartStore());

      act(() => {
        result.current.setRestaurantId(123);
      });

      expect(result.current.restaurantId).toBe(123);
    });
  });

  describe('Promotions and Discounts', () => {
    test('applies promo code', () => {
      const { result } = renderHook(() => useCartStore());

      act(() => {
        result.current.applyPromoCode('SAVE10', 10);
      });

      expect(result.current.appliedPromoCode).toBe('SAVE10');
      expect(result.current.discount).toBe(10);
    });

    test('removes promo code', () => {
      const { result } = renderHook(() => useCartStore());

      act(() => {
        result.current.applyPromoCode('SAVE10', 10);
        result.current.removePromoCode();
      });

      expect(result.current.appliedPromoCode).toBeNull();
      expect(result.current.discount).toBe(0);
    });
  });

  describe('Cart Calculations', () => {
    test('calculates subtotal correctly', () => {
      const { result } = renderHook(() => useCartStore());

      act(() => {
        result.current.addItem({ id: 1, name: 'Burger', price: 12.99 });
        result.current.addItem({ id: 2, name: 'Pizza', price: 15.99 });
      });

      const subtotal = result.current.getSubtotal();
      expect(subtotal).toBe(28.98);
    });

    test('calculates subtotal with quantities', () => {
      const { result } = renderHook(() => useCartStore());

      act(() => {
        result.current.addItem({ id: 1, name: 'Burger', price: 10.00 });
      });

      const cartId = result.current.items[0].cartId;

      act(() => {
        result.current.updateItemQuantity(cartId, 3);
      });

      const subtotal = result.current.getSubtotal();
      expect(subtotal).toBe(30.00);
    });

    test('calculates total with tax', () => {
      const { result } = renderHook(() => useCartStore());

      act(() => {
        result.current.addItem({ id: 1, name: 'Burger', price: 100.00 });
      });

      const total = result.current.getTotal(); // Uses built-in tax rate
      // 100 * 1.0875 = 108.75
      expect(total).toBe(108.75);
    });

    test('calculates total with discount', () => {
      const { result } = renderHook(() => useCartStore());

      act(() => {
        result.current.addItem({ id: 1, name: 'Burger', price: 100.00 });
        result.current.applyPromoCode('SAVE20', 20);
      });

      const total = result.current.getTotal(); // Uses built-in tax rate
      // 100 + (100 * 0.0875) - 20 = 88.75
      expect(total).toBe(88.75);
    });

    test('returns 0 for empty cart', () => {
      const { result } = renderHook(() => useCartStore());

      expect(result.current.getSubtotal()).toBe(0);
      expect(result.current.getTotal()).toBe(0);
    });
  });
});