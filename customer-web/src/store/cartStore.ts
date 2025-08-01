import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { CartItem, MenuItem, Modifier } from '../types';

interface CartState {
  items: CartItem[];
  
  // Computed values
  getTotal: () => number;
  getItemCount: () => number;
  
  // Actions
  addItem: (menuItem: MenuItem, quantity: number, modifiers?: Modifier[], specialInstructions?: string) => void;
  updateItemQuantity: (menuItemId: number, quantity: number) => void;
  removeItem: (menuItemId: number) => void;
  clearCart: () => void;
  getItem: (menuItemId: number) => CartItem | undefined;
}

export const useCartStore = create<CartState>()(
  persist(
    (set, get) => ({
      items: [],

      getTotal: () => {
        const { items } = get();
        return items.reduce((total, item) => total + item.subtotal, 0);
      },

      getItemCount: () => {
        const { items } = get();
        return items.reduce((count, item) => count + item.quantity, 0);
      },

      addItem: (menuItem, quantity, modifiers = [], specialInstructions = '') => {
        set((state) => {
          const existingItem = state.items.find(
            (item) => item.menuItem.id === menuItem.id
          );

          if (existingItem) {
            // Update quantity if item already exists
            return {
              items: state.items.map((item) =>
                item.menuItem.id === menuItem.id
                  ? {
                      ...item,
                      quantity: item.quantity + quantity,
                      subtotal: (item.quantity + quantity) * (menuItem.price + calculateModifierPrice(modifiers)),
                    }
                  : item
              ),
            };
          }

          // Add new item
          const modifierPrice = calculateModifierPrice(modifiers);
          const subtotal = quantity * (menuItem.price + modifierPrice);

          return {
            items: [
              ...state.items,
              {
                menuItem,
                quantity,
                modifiers,
                specialInstructions,
                subtotal,
              },
            ],
          };
        });
      },

      updateItemQuantity: (menuItemId, quantity) => {
        if (quantity <= 0) {
          get().removeItem(menuItemId);
          return;
        }

        set((state) => ({
          items: state.items.map((item) =>
            item.menuItem.id === menuItemId
              ? {
                  ...item,
                  quantity,
                  subtotal: quantity * (item.menuItem.price + calculateModifierPrice(item.modifiers || [])),
                }
              : item
          ),
        }));
      },

      removeItem: (menuItemId) => {
        set((state) => ({
          items: state.items.filter((item) => item.menuItem.id !== menuItemId),
        }));
      },

      clearCart: () => {
        set({ items: [] });
      },

      getItem: (menuItemId) => {
        const { items } = get();
        return items.find((item) => item.menuItem.id === menuItemId);
      },
    }),
    {
      name: 'cart-storage',
    }
  )
);

// Helper function to calculate total modifier price
function calculateModifierPrice(modifiers: Modifier[]): number {
  return modifiers.reduce((total, modifier) => total + modifier.price_adjustment, 0);
}