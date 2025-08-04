import { renderHook, act } from '@testing-library/react';
import { useCartStore } from '../cartStore';
import { MenuItem, Modifier } from '../../types';

const mockMenuItem: MenuItem = {
  id: 1,
  category_id: 1,
  name: 'Test Burger',
  description: 'A test burger',
  price: 12.99,
  is_active: true,
  is_available: true,
  display_order: 1,
};

const mockModifier: Modifier = {
  id: 1,
  name: 'Extra cheese',
  price_adjustment: 2.00,
  is_available: true,
};

describe('cartStore', () => {
  beforeEach(() => {
    // Clear the store before each test
    const { result } = renderHook(() => useCartStore());
    act(() => {
      result.current.clearCart();
    });
  });

  test('should add item to cart', () => {
    const { result } = renderHook(() => useCartStore());

    act(() => {
      result.current.addItem(mockMenuItem, 2);
    });

    expect(result.current.items).toHaveLength(1);
    expect(result.current.items[0].menuItem.id).toBe(1);
    expect(result.current.items[0].quantity).toBe(2);
    expect(result.current.getItemCount()).toBe(2);
  });

  test('should update quantity when adding same item', () => {
    const { result } = renderHook(() => useCartStore());

    act(() => {
      result.current.addItem(mockMenuItem, 1);
      result.current.addItem(mockMenuItem, 2);
    });

    expect(result.current.items).toHaveLength(1);
    expect(result.current.items[0].quantity).toBe(3);
  });

  test('should calculate total correctly', () => {
    const { result } = renderHook(() => useCartStore());

    act(() => {
      result.current.addItem(mockMenuItem, 2);
    });

    expect(result.current.getTotal()).toBe(25.98); // 12.99 * 2
  });

  test('should calculate total with modifiers', () => {
    const { result } = renderHook(() => useCartStore());

    act(() => {
      result.current.addItem(mockMenuItem, 1, [mockModifier]);
    });

    expect(result.current.getTotal()).toBe(14.99); // 12.99 + 2.00
  });

  test('should update item quantity', () => {
    const { result } = renderHook(() => useCartStore());

    act(() => {
      result.current.addItem(mockMenuItem, 1);
      result.current.updateItemQuantity(1, 5);
    });

    expect(result.current.items[0].quantity).toBe(5);
    expect(result.current.getTotal()).toBe(64.95); // 12.99 * 5
  });

  test('should remove item when quantity is 0', () => {
    const { result } = renderHook(() => useCartStore());

    act(() => {
      result.current.addItem(mockMenuItem, 1);
      result.current.updateItemQuantity(1, 0);
    });

    expect(result.current.items).toHaveLength(0);
  });

  test('should remove item from cart', () => {
    const { result } = renderHook(() => useCartStore());

    act(() => {
      result.current.addItem(mockMenuItem, 1);
      result.current.removeItem(1);
    });

    expect(result.current.items).toHaveLength(0);
  });

  test('should clear cart', () => {
    const { result } = renderHook(() => useCartStore());

    act(() => {
      result.current.addItem(mockMenuItem, 1);
      result.current.addItem({ ...mockMenuItem, id: 2 }, 2);
      result.current.clearCart();
    });

    expect(result.current.items).toHaveLength(0);
    expect(result.current.getTotal()).toBe(0);
  });

  test('should get specific item', () => {
    const { result } = renderHook(() => useCartStore());

    act(() => {
      result.current.addItem(mockMenuItem, 1);
    });

    const item = result.current.getItem(1);
    expect(item?.menuItem.id).toBe(1);
    expect(item?.quantity).toBe(1);
  });

  test('should store special instructions', () => {
    const { result } = renderHook(() => useCartStore());

    act(() => {
      result.current.addItem(mockMenuItem, 1, [], 'No pickles');
    });

    expect(result.current.items[0].specialInstructions).toBe('No pickles');
  });
});